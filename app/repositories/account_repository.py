"""Hesap veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_ACCOUNT_SELECT = """
    SELECT
        a.id,
        a.bank_id,
        a.name,
        a.currency_id,
        a.opening_balance,
        a.current_balance,
        a.tracking_mode,
        a.is_active,
        a.note,
        a.created_at,
        a.updated_at,
        a.deleted_at,
        b.name AS bank_name,
        c.code AS currency_code,
        c.symbol AS currency_symbol,
        c.scale AS currency_scale
    FROM accounts a
    INNER JOIN banks b ON b.id = a.bank_id AND b.deleted_at IS NULL
    INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
    WHERE a.deleted_at IS NULL
"""


class AccountRepository:
    """accounts tablosu CRUD işlemleri."""

    def list_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = _ACCOUNT_SELECT
        if not include_inactive:
            sql += " AND a.is_active = 1"
        sql += " ORDER BY b.name, a.name"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesaplar listelenemedi.")

    def list_accounts_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        sql = _ACCOUNT_SELECT + " AND a.bank_id = ?"
        if not include_inactive:
            sql += " AND a.is_active = 1"
        sql += " ORDER BY a.name"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (bank_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka hesapları listelenemedi.")

    def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        sql = _ACCOUNT_SELECT + " AND a.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (account_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap okunamadı.")

    def create_account(
        self,
        bank_id: int,
        name: str,
        currency_id: int,
        opening_balance: int,
        tracking_mode: str = "ledger",
        note: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO accounts (
                bank_id, name, currency_id, opening_balance,
                current_balance, tracking_mode, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        bank_id,
                        name,
                        currency_id,
                        opening_balance,
                        opening_balance,
                        tracking_mode,
                        note,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"Bu bankada '{name}' adlı hesap zaten mevcut."
            ) from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap oluşturulamadı.")

    def update_account(
        self,
        account_id: int,
        bank_id: int,
        name: str,
        currency_id: int,
        opening_balance: int,
        current_balance: int,
        tracking_mode: str,
        is_active: bool,
        note: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE accounts
            SET bank_id = ?, name = ?, currency_id = ?,
                opening_balance = ?, current_balance = ?,
                tracking_mode = ?, is_active = ?, note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        bank_id,
                        name,
                        currency_id,
                        opening_balance,
                        current_balance,
                        tracking_mode,
                        int(is_active),
                        note,
                        account_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Hesap bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"Bu bankada '{name}' adlı hesap zaten mevcut."
            ) from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap güncellenemedi.")

    def soft_delete_account(
        self,
        account_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE accounts
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (account_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Hesap bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap silinemedi.")

    def count_accounts_by_currency(self, currency_id: int) -> int:
        sql = """
            SELECT COUNT(*) AS total
            FROM accounts
            WHERE currency_id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (currency_id,)).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi hesap sayısı okunamadı.")

    def get_account_with_currency(
        self,
        account_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Dict[str, Any]]:
        sql = _ACCOUNT_SELECT + " AND a.id = ?"
        try:
            if conn is not None:
                row = conn.execute(sql, (account_id,)).fetchone()
                return _row_to_dict(row) if row else None
            with get_connection() as connection:
                row = connection.execute(sql, (account_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap okunamadı.")

    def get_account_balance(
        self,
        account_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            SELECT current_balance
            FROM accounts
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            if conn is not None:
                row = conn.execute(sql, (account_id,)).fetchone()
            else:
                with get_connection() as connection:
                    row = connection.execute(sql, (account_id,)).fetchone()
            if row is None:
                raise NotFoundError("Hesap bulunamadı.")
            return int(row["current_balance"])
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap bakiyesi okunamadı.")

    def adjust_balance(
        self,
        account_id: int,
        delta_amount: int,
        conn: sqlite3.Connection,
    ) -> None:
        sql = """
            UPDATE accounts
            SET current_balance = current_balance + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            cursor = conn.execute(sql, (delta_amount, account_id))
            if cursor.rowcount == 0:
                raise NotFoundError("Hesap bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap bakiyesi güncellenemedi.")

    def set_current_balance(
        self,
        account_id: int,
        balance: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE accounts
            SET current_balance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            if conn is not None:
                cursor = conn.execute(sql, (balance, account_id))
            else:
                with get_connection() as connection:
                    cursor = connection.execute(sql, (balance, account_id))
                    if cursor.rowcount == 0:
                        raise NotFoundError("Hesap bulunamadı.")
                    return
            if cursor.rowcount == 0:
                raise NotFoundError("Hesap bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap bakiyesi güncellenemedi.")
