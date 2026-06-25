"""Para hareketi veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_TRANSACTION_SELECT = """
    SELECT
        t.id,
        t.account_id,
        t.txn_date,
        t.direction,
        t.total_amount,
        t.description,
        t.affects_balance,
        t.source_type,
        t.source_id,
        t.created_at,
        t.updated_at,
        t.deleted_at,
        a.name AS account_name,
        a.tracking_mode,
        b.name AS bank_name,
        c.code AS currency_code,
        c.scale AS currency_scale
    FROM transactions t
    INNER JOIN accounts a ON a.id = t.account_id AND a.deleted_at IS NULL
    INNER JOIN banks b ON b.id = a.bank_id AND b.deleted_at IS NULL
    INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
    WHERE t.deleted_at IS NULL
"""

_LINE_SELECT = """
    SELECT
        id,
        transaction_id,
        nature,
        category_id,
        asset_id,
        amount,
        note,
        deleted_at
    FROM transaction_lines
    WHERE deleted_at IS NULL
"""


class TransactionRepository:
    """transactions ve transaction_lines tabloları."""

    def list_transactions(self) -> List[Dict[str, Any]]:
        sql = _TRANSACTION_SELECT + " ORDER BY t.txn_date DESC, t.id DESC"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlemler listelenemedi.")

    def list_transactions_by_account(self, account_id: int) -> List[Dict[str, Any]]:
        sql = _TRANSACTION_SELECT + " AND t.account_id = ? ORDER BY t.txn_date DESC, t.id DESC"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (account_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap işlemleri listelenemedi.")

    def get_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        sql = _TRANSACTION_SELECT + " AND t.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (transaction_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem okunamadı.")

    def get_transaction_with_lines(
        self,
        transaction_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Dict[str, Any]]:
        txn_sql = _TRANSACTION_SELECT + " AND t.id = ?"
        lines_sql = _LINE_SELECT + " AND transaction_id = ? ORDER BY id"
        try:
            if conn is not None:
                row = conn.execute(txn_sql, (transaction_id,)).fetchone()
                if row is None:
                    return None
                txn = _row_to_dict(row)
                line_rows = conn.execute(lines_sql, (transaction_id,)).fetchall()
            else:
                with get_connection() as connection:
                    row = connection.execute(txn_sql, (transaction_id,)).fetchone()
                    if row is None:
                        return None
                    txn = _row_to_dict(row)
                    line_rows = connection.execute(lines_sql, (transaction_id,)).fetchall()
            txn["lines"] = [_row_to_dict(line) for line in line_rows]
            return txn
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem detayı okunamadı.")

    def get_transaction_lines(self, transaction_id: int) -> List[Dict[str, Any]]:
        sql = _LINE_SELECT + " AND transaction_id = ? ORDER BY id"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (transaction_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem satırları okunamadı.")

    def list_transactions_by_source(
        self,
        source_type: str,
        source_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        sql = (
            _TRANSACTION_SELECT
            + " AND t.source_type = ? AND t.source_id = ? ORDER BY t.id"
        )
        try:
            if conn is not None:
                rows = conn.execute(sql, (source_type, source_id)).fetchall()
            else:
                with get_connection() as connection:
                    rows = connection.execute(sql, (source_type, source_id)).fetchall()
            return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kaynak işlemleri listelenemedi.")

    def get_balance_totals_for_account(self, account_id: int) -> Tuple[int, int]:
        sql = """
            SELECT direction, COALESCE(SUM(total_amount), 0) AS total
            FROM transactions
            WHERE account_id = ?
              AND deleted_at IS NULL
              AND affects_balance = 1
            GROUP BY direction
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (account_id,)).fetchall()
                in_total = 0
                out_total = 0
                for row in rows:
                    if row["direction"] == "in":
                        in_total = int(row["total"])
                    elif row["direction"] == "out":
                        out_total = int(row["total"])
                return in_total, out_total
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem toplamları okunamadı.")

    def create_transaction_with_lines(
        self,
        account_id: int,
        txn_date: str,
        direction: str,
        total_amount: int,
        description: Optional[str],
        affects_balance: bool,
        source_type: Optional[str],
        source_id: Optional[int],
        lines: List[Dict[str, Any]],
        conn: sqlite3.Connection,
    ) -> int:
        insert_txn_sql = """
            INSERT INTO transactions (
                account_id, txn_date, direction, total_amount, description,
                affects_balance, source_type, source_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        insert_line_sql = """
            INSERT INTO transaction_lines (
                transaction_id, nature, category_id, asset_id, amount, note
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            cursor = conn.execute(
                insert_txn_sql,
                (
                    account_id,
                    txn_date,
                    direction,
                    total_amount,
                    description,
                    int(affects_balance),
                    source_type,
                    source_id,
                ),
            )
            transaction_id = int(cursor.lastrowid)
            for line in lines:
                conn.execute(
                    insert_line_sql,
                    (
                        transaction_id,
                        line["nature"],
                        line.get("category_id"),
                        line.get("asset_id"),
                        line["amount"],
                        line.get("note"),
                    ),
                )
            return transaction_id
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem oluşturulamadı.")

    def update_transaction_with_lines(
        self,
        transaction_id: int,
        account_id: int,
        txn_date: str,
        direction: str,
        total_amount: int,
        description: Optional[str],
        affects_balance: bool,
        lines: List[Dict[str, Any]],
        conn: sqlite3.Connection,
    ) -> None:
        update_txn_sql = """
            UPDATE transactions
            SET account_id = ?, txn_date = ?, direction = ?, total_amount = ?,
                description = ?, affects_balance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        soft_delete_lines_sql = """
            UPDATE transaction_lines
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ? AND deleted_at IS NULL
        """
        insert_line_sql = """
            INSERT INTO transaction_lines (
                transaction_id, nature, category_id, asset_id, amount, note
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            cursor = conn.execute(
                update_txn_sql,
                (
                    account_id,
                    txn_date,
                    direction,
                    total_amount,
                    description,
                    int(affects_balance),
                    transaction_id,
                ),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("İşlem bulunamadı.")
            conn.execute(soft_delete_lines_sql, (transaction_id,))
            for line in lines:
                conn.execute(
                    insert_line_sql,
                    (
                        transaction_id,
                        line["nature"],
                        line.get("category_id"),
                        line.get("asset_id"),
                        line["amount"],
                        line.get("note"),
                    ),
                )
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem güncellenemedi.")

    def soft_delete_transaction(
        self,
        transaction_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        soft_delete_txn_sql = """
            UPDATE transactions
            SET deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        soft_delete_lines_sql = """
            UPDATE transaction_lines
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ? AND deleted_at IS NULL
        """
        try:
            cursor = conn.execute(soft_delete_txn_sql, (transaction_id,))
            if cursor.rowcount == 0:
                raise NotFoundError("İşlem bulunamadı.")
            conn.execute(soft_delete_lines_sql, (transaction_id,))
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "İşlem silinemedi.")
