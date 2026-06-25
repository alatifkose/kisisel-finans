"""SQLite veritabanı bağlantısı ve şema yönetimi."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable, Optional

from app.core.exceptions import AppError

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "finance.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

BASE_SCHEMA_VERSION = 1


class DatabaseError(AppError):
    """Veritabanı işlemi hatası."""


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """SQLite bağlantısı aç; foreign key desteğini etkinleştir."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Mevcut bağlantı üzerinde transaction yönetimi."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _read_sql_file(path: Path) -> str:
    if not path.exists():
        raise DatabaseError(f"SQL dosyası bulunamadı: {path}")
    return path.read_text(encoding="utf-8")


def _get_current_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
    if row is None or row["version"] is None:
        return 0
    return int(row["version"])


def _apply_schema_sql(conn: sqlite3.Connection) -> None:
    sql = _read_sql_file(SCHEMA_PATH)
    conn.executescript(sql)


def _record_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)",
        (version,),
    )


def _discover_migrations() -> list[tuple[int, Path]]:
    if not MIGRATIONS_DIR.exists():
        return []

    migrations: list[tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        prefix = path.stem.split("_", 1)[0]
        if not prefix.isdigit():
            raise DatabaseError(f"Geçersiz migration dosya adı: {path.name}")
        migrations.append((int(prefix), path))

    migrations.sort(key=lambda item: item[0])
    return migrations


def _latest_schema_version() -> int:
    """schema.sql'in karşılık geldiği sürüm = en yüksek migration numarası."""
    migrations = _discover_migrations()
    if not migrations:
        return BASE_SCHEMA_VERSION
    return max(version for version, _ in migrations)


def _schema_version_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    return row is not None


def _run_migrations(conn: sqlite3.Connection) -> None:
    current_version = _get_current_schema_version(conn)
    for version, path in _discover_migrations():
        if version <= current_version:
            continue
        sql = _read_sql_file(path)
        conn.executescript(sql)
        _record_schema_version(conn, version)


def init_database() -> None:
    """Veritabanını oluştur, şemayı uygula ve migration runner'ı çalıştır."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        # schema.sql daima nihai şemayı kurar. Boş bir veritabanında bu, tüm
        # migration'ların uygulanmış haline denktir; bu yüzden en yüksek
        # migration sürümünü "uygulanmış" damgalayıp redundant (ve 007 gibi
        # çakışan) migration'ların yeniden koşmasını engelliyoruz. Var olan
        # veritabanlarında ise migration runner normal şekilde eksikleri tamamlar.
        is_fresh = not _schema_version_table_exists(conn)
        _apply_schema_sql(conn)
        if is_fresh:
            _record_schema_version(conn, _latest_schema_version())
        elif _get_current_schema_version(conn) == 0:
            _record_schema_version(conn, BASE_SCHEMA_VERSION)
        _run_migrations(conn)


def get_database_path() -> Path:
    """Veritabanı dosya yolunu döndür."""
    return DB_PATH
