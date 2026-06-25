"""Banka özeti aggregate sorguları."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from app.core.database import get_connection
from app.core.exceptions import RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


class SummaryRepository:
    """Özet ekranı için salt okunur aggregate sorgular."""

    def get_cash_balances_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(a.current_balance), 0) AS total_balance,
                COUNT(a.id) AS account_count
            FROM accounts a
            INNER JOIN currencies c
                ON c.id = a.currency_id
                AND c.deleted_at IS NULL
                AND c.is_active = 1
            WHERE a.deleted_at IS NULL
              AND a.is_active = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Nakit bakiyeleri okunamadı.")

    def get_account_counts(self) -> Dict[str, int]:
        queries = {
            "active_bank_count": """
                SELECT COUNT(*) AS total FROM banks
                WHERE deleted_at IS NULL AND is_active = 1
            """,
            "active_account_count": """
                SELECT COUNT(*) AS total FROM accounts
                WHERE deleted_at IS NULL AND is_active = 1
            """,
            "ledger_account_count": """
                SELECT COUNT(*) AS total FROM accounts
                WHERE deleted_at IS NULL AND is_active = 1 AND tracking_mode = 'ledger'
            """,
            "snapshot_account_count": """
                SELECT COUNT(*) AS total FROM accounts
                WHERE deleted_at IS NULL AND is_active = 1 AND tracking_mode = 'snapshot'
            """,
        }
        try:
            with get_connection() as conn:
                result: Dict[str, int] = {}
                for key, sql in queries.items():
                    row = conn.execute(sql).fetchone()
                    result[key] = int(row["total"]) if row else 0
                return result
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap sayıları okunamadı.")

    def get_monthly_transaction_totals(
        self,
        year: int,
        month: int,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(CASE WHEN tl.nature = 'income' THEN tl.amount ELSE 0 END), 0)
                    AS income_total,
                COALESCE(SUM(CASE WHEN tl.nature = 'expense' THEN tl.amount ELSE 0 END), 0)
                    AS expense_total,
                COALESCE(SUM(CASE WHEN tl.nature = 'cost' THEN tl.amount ELSE 0 END), 0)
                    AS cost_total
            FROM transaction_lines tl
            INNER JOIN transactions t
                ON t.id = tl.transaction_id AND t.deleted_at IS NULL
            INNER JOIN accounts a
                ON a.id = t.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE tl.deleted_at IS NULL
              AND t.affects_balance = 1
              AND tl.nature IN ('income', 'expense', 'cost')
              AND strftime('%Y', t.txn_date) = ?
              AND strftime('%m', t.txn_date) = ?
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    sql,
                    (str(year), f"{month:02d}"),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Aylık işlem toplamları okunamadı.")

    def get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                t.id,
                t.txn_date,
                b.name AS bank_name,
                a.name AS account_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                t.direction,
                t.total_amount,
                t.description,
                t.source_type
            FROM transactions t
            INNER JOIN accounts a ON a.id = t.account_id AND a.deleted_at IS NULL
            INNER JOIN banks b ON b.id = a.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE t.deleted_at IS NULL
            ORDER BY t.txn_date DESC, t.id DESC
            LIMIT ?
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Son işlemler okunamadı.")

    def get_accounts_snapshot(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                a.id AS account_id,
                b.name AS bank_name,
                a.name AS account_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                a.current_balance,
                a.tracking_mode,
                a.is_active
            FROM accounts a
            INNER JOIN banks b ON b.id = a.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE a.deleted_at IS NULL
              AND a.is_active = 1
            ORDER BY b.name, a.name
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap özeti okunamadı.")
