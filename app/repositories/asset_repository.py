"""Varlık veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


class AssetRepository:
    """assets tablosu CRUD işlemleri."""

    def list_assets(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, name, type, is_active, deleted_at
            FROM assets
            WHERE deleted_at IS NULL
        """
        if not include_inactive:
            sql += " AND is_active = 1"
        sql += " ORDER BY name"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlıklar listelenemedi.")

    def get_asset(self, asset_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT id, name, type, is_active, deleted_at
            FROM assets
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (asset_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık okunamadı.")

    def create_asset(
        self,
        name: str,
        type_: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO assets (name, type)
            VALUES (?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (name, type_))
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{name}' varlığı zaten mevcut.") from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık oluşturulamadı.")

    def update_asset(
        self,
        asset_id: int,
        name: str,
        type_: str,
        is_active: bool,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE assets
            SET name = ?, type = ?, is_active = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (name, type_, int(is_active), asset_id))
                if cursor.rowcount == 0:
                    raise NotFoundError("Varlık bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{name}' varlığı zaten mevcut.") from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık güncellenemedi.")

    def soft_delete_asset(
        self,
        asset_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE assets
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (asset_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Varlık bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık silinemedi.")
