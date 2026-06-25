"""Banka veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


class BankRepository:
    """banks tablosu CRUD işlemleri."""

    def list_banks(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, name, short_name, is_active, note, created_at, updated_at, deleted_at
            FROM banks
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
            _handle_sqlite_error(exc, "Bankalar listelenemedi.")

    def get_bank(self, bank_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT id, name, short_name, is_active, note, created_at, updated_at, deleted_at
            FROM banks
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (bank_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka okunamadı.")

    def create_bank(
        self,
        name: str,
        short_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> int:
        sql = """
            INSERT INTO banks (name, short_name, note)
            VALUES (?, ?, ?)
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (name, short_name, note))
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{name}' bankası zaten mevcut.") from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka oluşturulamadı.")

    def update_bank(
        self,
        bank_id: int,
        name: str,
        short_name: Optional[str] = None,
        is_active: bool = True,
        note: Optional[str] = None,
    ) -> None:
        sql = """
            UPDATE banks
            SET name = ?, short_name = ?, is_active = ?, note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (name, short_name, int(is_active), note, bank_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Banka bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{name}' bankası zaten mevcut.") from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka güncellenemedi.")

    def soft_delete_bank(self, bank_id: int) -> None:
        sql = """
            UPDATE banks
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (bank_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Banka bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka silinemedi.")

    def count_active_accounts(self, bank_id: int) -> int:
        sql = """
            SELECT COUNT(*) AS total
            FROM accounts
            WHERE bank_id = ? AND deleted_at IS NULL AND is_active = 1
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (bank_id,)).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka hesap sayısı okunamadı.")
