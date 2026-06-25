"""Transfer veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_TRANSFER_SELECT = """
    SELECT
        tr.id,
        tr.transfer_date,
        tr.from_account_id,
        fb.name AS from_bank_name,
        fa.name AS from_account_name,
        tr.from_currency_id,
        fc.code AS from_currency_code,
        fc.symbol AS from_currency_symbol,
        fc.scale AS from_scale,
        tr.from_amount,
        tr.to_account_id,
        tb.name AS to_bank_name,
        ta.name AS to_account_name,
        tr.to_currency_id,
        tc.code AS to_currency_code,
        tc.symbol AS to_currency_symbol,
        tc.scale AS to_scale,
        tr.to_amount,
        tr.exchange_rate,
        tr.description,
        tr.created_at,
        tr.updated_at,
        tr.deleted_at
    FROM transfers tr
    INNER JOIN accounts fa ON fa.id = tr.from_account_id AND fa.deleted_at IS NULL
    INNER JOIN banks fb ON fb.id = fa.bank_id AND fb.deleted_at IS NULL
    INNER JOIN currencies fc ON fc.id = tr.from_currency_id AND fc.deleted_at IS NULL
    INNER JOIN accounts ta ON ta.id = tr.to_account_id AND ta.deleted_at IS NULL
    INNER JOIN banks tb ON tb.id = ta.bank_id AND tb.deleted_at IS NULL
    INNER JOIN currencies tc ON tc.id = tr.to_currency_id AND tc.deleted_at IS NULL
    WHERE tr.deleted_at IS NULL
"""


class TransferRepository:
    """transfers tablosu."""

    def list_transfers(self) -> List[Dict[str, Any]]:
        sql = _TRANSFER_SELECT + " ORDER BY tr.transfer_date DESC, tr.id DESC"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transferler listelenemedi.")

    def get_transfer(self, transfer_id: int) -> Optional[Dict[str, Any]]:
        sql = _TRANSFER_SELECT + " AND tr.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (transfer_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transfer okunamadı.")

    def get_transfer_with_details(
        self,
        transfer_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Dict[str, Any]]:
        sql = _TRANSFER_SELECT + " AND tr.id = ?"
        try:
            if conn is not None:
                row = conn.execute(sql, (transfer_id,)).fetchone()
                return _row_to_dict(row) if row else None
            with get_connection() as connection:
                row = connection.execute(sql, (transfer_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transfer detayı okunamadı.")

    def list_transfers_by_account(self, account_id: int) -> List[Dict[str, Any]]:
        sql = (
            _TRANSFER_SELECT
            + " AND (tr.from_account_id = ? OR tr.to_account_id = ?)"
            + " ORDER BY tr.transfer_date DESC, tr.id DESC"
        )
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (account_id, account_id)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap transferleri listelenemedi.")

    def list_transfers_by_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = (
            _TRANSFER_SELECT
            + " AND tr.transfer_date >= ? AND tr.transfer_date <= ?"
            + " ORDER BY tr.transfer_date DESC, tr.id DESC"
        )
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Tarih aralığı transferleri listelenemedi.")

    def create_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        from_amount: int,
        from_currency_id: int,
        to_amount: int,
        to_currency_id: int,
        exchange_rate: Optional[float],
        transfer_date: str,
        description: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO transfers (
                from_account_id, to_account_id,
                from_amount, from_currency_id,
                to_amount, to_currency_id,
                exchange_rate, transfer_date, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            from_account_id,
            to_account_id,
            from_amount,
            from_currency_id,
            to_amount,
            to_currency_id,
            exchange_rate,
            transfer_date,
            description,
        )
        try:
            if conn is not None:
                cursor = conn.execute(sql, params)
                return int(cursor.lastrowid)
            with get_connection() as connection:
                cursor = connection.execute(sql, params)
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transfer oluşturulamadı.")

    def soft_delete_transfer(
        self,
        transfer_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE transfers
            SET deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            if conn is not None:
                cursor = conn.execute(sql, (transfer_id,))
            else:
                with get_connection() as connection:
                    cursor = connection.execute(sql, (transfer_id,))
                    if cursor.rowcount == 0:
                        raise NotFoundError("Transfer bulunamadı.")
                    return
            if cursor.rowcount == 0:
                raise NotFoundError("Transfer bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transfer silinemedi.")
