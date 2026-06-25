"""Rapor aggregate sorguları."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from app.core.constants import InstallmentStatus
from app.core.database import get_connection
from app.core.exceptions import RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_CASHFLOW_BASE = """
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
"""


class ReportRepository:
    """Raporlar için salt okunur aggregate sorgular."""

    def get_cashflow_by_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        sql = f"""
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
            {_CASHFLOW_BASE}
              AND strftime('%Y', t.txn_date) = ?
              AND strftime('%m', t.txn_date) = ?
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (str(year), f"{month:02d}")).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Aylık nakit akışı okunamadı.")

    def get_cashflow_by_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = f"""
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
            {_CASHFLOW_BASE}
              AND t.txn_date >= ? AND t.txn_date <= ?
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Tarih aralığı nakit akışı okunamadı.")

    def get_category_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                cat.id AS category_id,
                cat.name AS category_name,
                cat.nature AS nature,
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(tl.amount), 0) AS total_amount,
                COUNT(DISTINCT t.id) AS transaction_count
            FROM transaction_lines tl
            INNER JOIN transactions t
                ON t.id = tl.transaction_id AND t.deleted_at IS NULL
            INNER JOIN accounts a
                ON a.id = t.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = a.currency_id AND c.deleted_at IS NULL
            INNER JOIN categories cat
                ON cat.id = tl.category_id AND cat.deleted_at IS NULL
            WHERE tl.deleted_at IS NULL
              AND t.affects_balance = 1
              AND tl.nature IN ('income', 'expense', 'cost')
              AND tl.category_id IS NOT NULL
              AND t.txn_date >= ? AND t.txn_date <= ?
            GROUP BY cat.id, cat.name, cat.nature, c.id, c.code, c.symbol, c.scale
            ORDER BY cat.nature, cat.name, c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kategori raporu okunamadı.")

    def get_asset_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                COALESCE(ast.id, 0) AS asset_id,
                COALESCE(ast.name, 'Genel / Varlıksız') AS asset_name,
                COALESCE(ast.type, '—') AS asset_type,
                tl.nature AS nature,
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(tl.amount), 0) AS total_amount,
                COUNT(DISTINCT t.id) AS transaction_count
            FROM transaction_lines tl
            INNER JOIN transactions t
                ON t.id = tl.transaction_id AND t.deleted_at IS NULL
            INNER JOIN accounts a
                ON a.id = t.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = a.currency_id AND c.deleted_at IS NULL
            LEFT JOIN assets ast
                ON ast.id = tl.asset_id AND ast.deleted_at IS NULL
            WHERE tl.deleted_at IS NULL
              AND t.affects_balance = 1
              AND tl.nature IN ('income', 'expense', 'cost')
              AND t.txn_date >= ? AND t.txn_date <= ?
            GROUP BY ast.id, ast.name, ast.type, tl.nature,
                     c.id, c.code, c.symbol, c.scale
            ORDER BY asset_name, tl.nature, c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık raporu okunamadı.")

    def get_financing_expense_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                ct.id AS component_type_id,
                ct.code AS component_type_code,
                ct.name AS component_type_name,
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(ic.amount), 0) AS total_amount,
                COUNT(DISTINCT i.id) AS installment_count
            FROM installment_components ic
            INNER JOIN installments i
                ON i.id = ic.installment_id AND i.deleted_at IS NULL
            INNER JOIN debt_plans dp
                ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN component_types ct
                ON ct.id = ic.component_type_id AND ct.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE ic.deleted_at IS NULL
              AND ct.nature = 'expense'
              AND i.status = ?
              AND i.paid_date >= ? AND i.paid_date <= ?
            GROUP BY ct.id, ct.code, ct.name, c.id, c.code, c.symbol, c.scale
            HAVING total_amount != 0
            ORDER BY ct.name, c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    sql,
                    (InstallmentStatus.PAID, start_date, end_date),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Finansman gideri raporu okunamadı.")

    def get_financing_expense_details(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                dp.id AS plan_id,
                dp.name AS plan_name,
                dp.plan_kind,
                b.name AS bank_name,
                i.seq AS installment_seq,
                COALESCE(i.paid_date, i.due_date) AS payment_date,
                ct.code AS component_type_code,
                ct.name AS component_type_name,
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                ic.amount AS amount
            FROM installment_components ic
            INNER JOIN installments i
                ON i.id = ic.installment_id AND i.deleted_at IS NULL
            INNER JOIN debt_plans dp
                ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN banks b
                ON b.id = dp.bank_id AND b.deleted_at IS NULL
            INNER JOIN component_types ct
                ON ct.id = ic.component_type_id AND ct.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE ic.deleted_at IS NULL
              AND ct.nature = 'expense'
              AND i.status = ?
              AND i.paid_date >= ? AND i.paid_date <= ?
            ORDER BY payment_date, dp.name, i.seq, ct.name
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    sql,
                    (InstallmentStatus.PAID, start_date, end_date),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Finansman gideri detayı okunamadı.")

    def get_principal_payment_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(tl.amount), 0) AS total_principal_paid,
                COUNT(DISTINCT t.id) AS transaction_count
            FROM transaction_lines tl
            INNER JOIN transactions t
                ON t.id = tl.transaction_id AND t.deleted_at IS NULL
            INNER JOIN accounts a
                ON a.id = t.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE tl.deleted_at IS NULL
              AND tl.nature = 'principal'
              AND t.affects_balance = 1
              AND t.txn_date >= ? AND t.txn_date <= ?
            GROUP BY c.id, c.code, c.symbol, c.scale
            HAVING total_principal_paid != 0
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Anapara ödeme raporu okunamadı.")

    def get_transfer_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                tr.id,
                tr.transfer_date,
                fb.name AS from_bank_name,
                fa.name AS from_account_name,
                fc.code AS from_currency_code,
                fc.symbol AS from_currency_symbol,
                fc.scale AS from_scale,
                tr.from_amount,
                tb.name AS to_bank_name,
                ta.name AS to_account_name,
                tc.code AS to_currency_code,
                tc.symbol AS to_currency_symbol,
                tc.scale AS to_scale,
                tr.to_amount,
                tr.exchange_rate,
                tr.description
            FROM transfers tr
            INNER JOIN accounts fa ON fa.id = tr.from_account_id AND fa.deleted_at IS NULL
            INNER JOIN banks fb ON fb.id = fa.bank_id AND fb.deleted_at IS NULL
            INNER JOIN currencies fc ON fc.id = tr.from_currency_id AND fc.deleted_at IS NULL
            INNER JOIN accounts ta ON ta.id = tr.to_account_id AND ta.deleted_at IS NULL
            INNER JOIN banks tb ON tb.id = ta.bank_id AND tb.deleted_at IS NULL
            INNER JOIN currencies tc ON tc.id = tr.to_currency_id AND tc.deleted_at IS NULL
            WHERE tr.deleted_at IS NULL
              AND tr.transfer_date >= ? AND tr.transfer_date <= ?
            ORDER BY tr.transfer_date DESC, tr.id DESC
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Transfer raporu okunamadı.")

    def get_payment_calendar(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        installment_sql = """
            SELECT
                'installment' AS item_type,
                i.due_date AS item_date,
                dp.name || ' / ' || i.seq || '. taksit' AS title,
                b.name AS bank_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                i.total_amount AS amount,
                i.status AS status
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN banks b ON b.id = dp.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND i.status IN (?, ?)
              AND dp.is_active = 1
              AND i.due_date >= ? AND i.due_date <= ?
        """
        card_sql = """
            SELECT
                'card_statement' AS item_type,
                cs.due_date AS item_date,
                cc.name || ' Ekstre Son Ödeme' AS title,
                b.name AS bank_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                cs.min_payment AS amount,
                'statement' AS status
            FROM card_statements cs
            INNER JOIN credit_cards cc ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL
            INNER JOIN banks b ON b.id = cc.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.deleted_at IS NULL
              AND cc.is_active = 1
              AND cs.due_date IS NOT NULL
              AND cs.due_date >= ? AND cs.due_date <= ?
        """
        try:
            with get_connection() as conn:
                inst_rows = conn.execute(
                    installment_sql,
                    (
                        InstallmentStatus.PLANNED,
                        InstallmentStatus.PARTIAL,
                        start_date,
                        end_date,
                    ),
                ).fetchall()
                card_rows = conn.execute(
                    card_sql,
                    (start_date, end_date),
                ).fetchall()
                combined = [_row_to_dict(row) for row in inst_rows]
                combined.extend(_row_to_dict(row) for row in card_rows)
                combined.sort(key=lambda r: (r["item_date"], r["title"]))
                return combined
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ödeme takvimi okunamadı.")

    def get_overdue_payments(self, as_of_date: str) -> List[Dict[str, Any]]:
        installment_sql = """
            SELECT
                'installment' AS item_type,
                i.due_date AS item_date,
                dp.name || ' / ' || i.seq || '. taksit' AS title,
                b.name AS bank_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                i.total_amount AS amount,
                i.status AS status
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN banks b ON b.id = dp.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND i.status != ?
              AND dp.is_active = 1
              AND i.due_date < ?
        """
        card_sql = """
            SELECT
                'card_statement' AS item_type,
                cs.due_date AS item_date,
                cc.name || ' Ekstre Son Ödeme' AS title,
                b.name AS bank_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                cs.min_payment AS amount,
                'overdue' AS status
            FROM card_statements cs
            INNER JOIN credit_cards cc ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL
            INNER JOIN banks b ON b.id = cc.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.deleted_at IS NULL
              AND cc.is_active = 1
              AND cs.due_date IS NOT NULL
              AND cs.due_date < ?
        """
        try:
            with get_connection() as conn:
                inst_rows = conn.execute(
                    installment_sql,
                    (InstallmentStatus.PAID, as_of_date),
                ).fetchall()
                card_rows = conn.execute(card_sql, (as_of_date,)).fetchall()
                combined = [_row_to_dict(row) for row in inst_rows]
                combined.extend(_row_to_dict(row) for row in card_rows)
                combined.sort(key=lambda r: (r["item_date"], r["title"]))
                return combined
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Gecikmiş ödemeler okunamadı.")
