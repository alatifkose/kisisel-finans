"""Para birimi veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


class CurrencyRepository:
    """currencies tablosu CRUD işlemleri."""

    def list_currencies(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, code, symbol, scale, is_active, deleted_at
            FROM currencies
            WHERE deleted_at IS NULL
        """
        if not include_inactive:
            sql += " AND is_active = 1"
        sql += " ORDER BY code"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimleri listelenemedi.")

    def get_currency(self, currency_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT id, code, symbol, scale, is_active, deleted_at
            FROM currencies
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (currency_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi okunamadı.")

    def create_currency(self, code: str, symbol: str, scale: int) -> int:
        sql = """
            INSERT INTO currencies (code, symbol, scale)
            VALUES (?, ?, ?)
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (code, symbol, scale))
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{code}' para birimi kodu zaten kullanılıyor.") from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi oluşturulamadı.")

    def update_currency(
        self,
        currency_id: int,
        code: str,
        symbol: str,
        scale: int,
        is_active: bool,
    ) -> None:
        sql = """
            UPDATE currencies
            SET code = ?, symbol = ?, scale = ?, is_active = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (code, symbol, scale, int(is_active), currency_id))
                if cursor.rowcount == 0:
                    raise NotFoundError("Para birimi bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"'{code}' para birimi kodu zaten kullanılıyor.") from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi güncellenemedi.")

    def soft_delete_currency(self, currency_id: int) -> None:
        sql = """
            UPDATE currencies
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (currency_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Para birimi bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi silinemedi.")
