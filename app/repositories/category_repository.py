"""Kategori veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


class CategoryRepository:
    """categories tablosu CRUD işlemleri."""

    def list_categories(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id,
                c.name,
                c.nature,
                c.parent_id,
                p.name AS parent_name,
                c.is_active,
                c.deleted_at
            FROM categories c
            LEFT JOIN categories p ON p.id = c.parent_id AND p.deleted_at IS NULL
            WHERE c.deleted_at IS NULL
        """
        if not include_inactive:
            sql += " AND c.is_active = 1"
        sql += " ORDER BY c.name"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategoriler listelenemedi.")

    def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT
                c.id,
                c.name,
                c.nature,
                c.parent_id,
                p.name AS parent_name,
                c.is_active,
                c.deleted_at
            FROM categories c
            LEFT JOIN categories p ON p.id = c.parent_id AND p.deleted_at IS NULL
            WHERE c.id = ? AND c.deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (category_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategori okunamadı.")

    def create_category(
        self,
        name: str,
        nature: str,
        parent_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO categories (name, nature, parent_id)
            VALUES (?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (name, nature, parent_id))
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' kategorisi ({nature}) zaten mevcut."
            ) from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategori oluşturulamadı.")

    def update_category(
        self,
        category_id: int,
        name: str,
        nature: str,
        parent_id: Optional[int],
        is_active: bool,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE categories
            SET name = ?, nature = ?, parent_id = ?, is_active = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (name, nature, parent_id, int(is_active), category_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Kategori bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' kategorisi ({nature}) zaten mevcut."
            ) from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategori güncellenemedi.")

    def soft_delete_category(
        self,
        category_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE categories
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (category_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Kategori bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategori silinemedi.")
