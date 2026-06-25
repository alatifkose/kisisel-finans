"""Taksit bileşen tipi veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_SELECT = """
    SELECT
        ct.id,
        ct.code,
        ct.name,
        ct.nature,
        ct.default_category_id,
        ct.is_active,
        ct.deleted_at,
        cat.name AS default_category_name
    FROM component_types ct
    LEFT JOIN categories cat
        ON cat.id = ct.default_category_id AND cat.deleted_at IS NULL
    WHERE ct.deleted_at IS NULL
"""


class ComponentTypeRepository:
    """component_types tablosu CRUD işlemleri."""

    def list_component_types(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = _SELECT
        if not include_inactive:
            sql += " AND ct.is_active = 1"
        sql += " ORDER BY ct.code"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Bileşen tipleri listelenemedi.")

    def get_component_type(self, component_type_id: int) -> Optional[Dict[str, Any]]:
        sql = _SELECT + " AND ct.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (component_type_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Bileşen tipi okunamadı.")

    def create_component_type(
        self,
        code: str,
        name: str,
        nature: str,
        default_category_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO component_types (code, name, nature, default_category_id)
            VALUES (?, ?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (code, name, nature, default_category_id),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{code}' bileşen tipi kodu zaten kullanılıyor.") from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Bileşen tipi oluşturulamadı.")

    def update_component_type(
        self,
        component_type_id: int,
        code: str,
        name: str,
        nature: str,
        is_active: bool,
        default_category_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE component_types
            SET code = ?, name = ?, nature = ?, is_active = ?, default_category_id = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (code, name, nature, int(is_active), default_category_id, component_type_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Bileşen tipi bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{code}' bileşen tipi kodu zaten kullanılıyor.") from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Bileşen tipi güncellenemedi.")

    def soft_delete_component_type(
        self,
        component_type_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE component_types
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (component_type_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Bileşen tipi bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Bileşen tipi silinemedi.")
