"""Borç planı veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.constants import InstallmentStatus
from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_PLAN_LIST_SELECT = """
    SELECT
        dp.id,
        dp.bank_id,
        dp.plan_kind,
        dp.name,
        dp.principal_amount,
        dp.currency_id,
        dp.interest_rate,
        dp.start_date,
        dp.installment_count,
        dp.is_active,
        dp.note,
        dp.source_card_id,
        dp.source_kmh_id,
        b.name AS bank_name,
        c.code AS currency_code,
        c.symbol AS currency_symbol,
        c.scale AS scale,
        cc.name AS source_card_name,
        kmh.name AS source_kmh_name,
        COALESCE((
            SELECT SUM(i.total_amount)
            FROM installments i
            WHERE i.debt_plan_id = dp.id
              AND i.deleted_at IS NULL
              AND i.status != ?
        ), 0) AS unpaid_total,
        COALESCE((
            SELECT SUM(i.total_amount)
            FROM installments i
            WHERE i.debt_plan_id = dp.id
              AND i.deleted_at IS NULL
              AND i.status = ?
        ), 0) AS paid_total,
        (
            SELECT MIN(i.due_date)
            FROM installments i
            WHERE i.debt_plan_id = dp.id
              AND i.deleted_at IS NULL
              AND i.status != ?
        ) AS next_due_date
    FROM debt_plans dp
    INNER JOIN banks b ON b.id = dp.bank_id AND b.deleted_at IS NULL
    INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
    LEFT JOIN credit_cards cc
        ON cc.id = dp.source_card_id AND cc.deleted_at IS NULL
    LEFT JOIN kmh_accounts kmh
        ON kmh.id = dp.source_kmh_id AND kmh.deleted_at IS NULL
    WHERE dp.deleted_at IS NULL
"""


class DebtPlanRepository:
    """debt_plans, installments ve installment_components tabloları."""

    def list_debt_plans(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._list_plans(include_inactive=include_inactive)

    def list_debt_plans_by_kind(
        self,
        plan_kind: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        return self._list_plans(plan_kind=plan_kind, include_inactive=include_inactive)

    def list_debt_plans_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        return self._list_plans(bank_id=bank_id, include_inactive=include_inactive)

    def _list_plans(
        self,
        plan_kind: Optional[str] = None,
        bank_id: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        sql = _PLAN_LIST_SELECT
        params: List[Any] = [
            InstallmentStatus.PAID,
            InstallmentStatus.PAID,
            InstallmentStatus.PAID,
        ]
        if not include_inactive:
            sql += " AND dp.is_active = 1"
        if plan_kind is not None:
            sql += " AND dp.plan_kind = ?"
            params.append(plan_kind)
        if bank_id is not None:
            sql += " AND dp.bank_id = ?"
            params.append(bank_id)
        sql += " ORDER BY dp.start_date DESC, dp.name"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Borç planları listelenemedi.")

    def get_debt_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        sql = _PLAN_LIST_SELECT + " AND dp.id = ?"
        params = [
            InstallmentStatus.PAID,
            InstallmentStatus.PAID,
            InstallmentStatus.PAID,
            plan_id,
        ]
        try:
            with get_connection() as conn:
                row = conn.execute(sql, params).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Borç planı okunamadı.")

    def get_installments_by_plan(self, plan_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                id, debt_plan_id, seq, due_date, total_amount,
                remaining_principal_after, status, paid_transaction_id,
                paid_date, note, deleted_at
            FROM installments
            WHERE debt_plan_id = ? AND deleted_at IS NULL
            ORDER BY seq
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (plan_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksitler okunamadı.")

    def get_installment_components(self, installment_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                ic.id,
                ic.installment_id,
                ic.component_type_id,
                ic.amount,
                ic.deleted_at,
                ct.code AS component_code,
                ct.name AS component_name,
                ct.nature AS component_nature,
                ct.default_category_id
            FROM installment_components ic
            INNER JOIN component_types ct
                ON ct.id = ic.component_type_id AND ct.deleted_at IS NULL
            WHERE ic.installment_id = ? AND ic.deleted_at IS NULL
            ORDER BY ic.id
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (installment_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksit bileşenleri okunamadı.")

    def get_debt_plan_with_installments(self, plan_id: int) -> Optional[Dict[str, Any]]:
        plan = self.get_debt_plan(plan_id)
        if plan is None:
            return None
        installments = self.get_installments_by_plan(plan_id)
        for inst in installments:
            inst["components"] = self.get_installment_components(int(inst["id"]))
        plan["installments"] = installments
        return plan

    def create_debt_plan_with_installments(
        self,
        bank_id: int,
        plan_kind: str,
        name: str,
        principal_amount: int,
        currency_id: int,
        interest_rate: Optional[float],
        start_date: Optional[str],
        installment_count: int,
        note: Optional[str],
        source_card_id: Optional[int],
        source_kmh_id: Optional[int],
        installments: List[Dict[str, Any]],
        conn: sqlite3.Connection,
    ) -> int:
        insert_plan_sql = """
            INSERT INTO debt_plans (
                bank_id, plan_kind, name, principal_amount, currency_id,
                interest_rate, start_date, installment_count, note,
                source_card_id, source_kmh_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        insert_inst_sql = """
            INSERT INTO installments (
                debt_plan_id, seq, due_date, total_amount,
                remaining_principal_after, status, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        insert_comp_sql = """
            INSERT INTO installment_components (
                installment_id, component_type_id, amount
            )
            VALUES (?, ?, ?)
        """
        try:
            cursor = conn.execute(
                insert_plan_sql,
                (
                    bank_id,
                    plan_kind,
                    name,
                    principal_amount,
                    currency_id,
                    interest_rate,
                    start_date,
                    installment_count,
                    note,
                    source_card_id,
                    source_kmh_id,
                ),
            )
            plan_id = int(cursor.lastrowid)
            for inst in installments:
                inst_cursor = conn.execute(
                    insert_inst_sql,
                    (
                        plan_id,
                        inst["seq"],
                        inst["due_date"],
                        inst["total_amount"],
                        inst.get("remaining_principal_after"),
                        InstallmentStatus.PLANNED,
                        inst.get("note"),
                    ),
                )
                installment_id = int(inst_cursor.lastrowid)
                for comp in inst["components"]:
                    conn.execute(
                        insert_comp_sql,
                        (
                            installment_id,
                            comp["component_type_id"],
                            comp["amount"],
                        ),
                    )
            return plan_id
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Borç planı oluşturulamadı.")

    def update_debt_plan_with_installments(
        self,
        plan_id: int,
        bank_id: int,
        plan_kind: str,
        name: str,
        principal_amount: int,
        currency_id: int,
        interest_rate: Optional[float],
        start_date: Optional[str],
        installment_count: int,
        is_active: bool,
        note: Optional[str],
        source_card_id: Optional[int],
        source_kmh_id: Optional[int],
        installments: List[Dict[str, Any]],
        conn: sqlite3.Connection,
    ) -> None:
        # AŞAMA 7 sonrası ödenmiş taksit içeren planlarda bu yöntem kısıtlanmalı
        # veya farklılaştırılmalı.
        update_plan_sql = """
            UPDATE debt_plans
            SET bank_id = ?, plan_kind = ?, name = ?, principal_amount = ?,
                currency_id = ?, interest_rate = ?, start_date = ?,
                installment_count = ?, is_active = ?, note = ?,
                source_card_id = ?,
                source_kmh_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        soft_delete_inst_sql = """
            UPDATE installments
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE debt_plan_id = ? AND deleted_at IS NULL
        """
        soft_delete_comp_sql = """
            UPDATE installment_components
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE installment_id IN (
                SELECT id FROM installments WHERE debt_plan_id = ?
            )
            AND deleted_at IS NULL
        """
        insert_inst_sql = """
            INSERT INTO installments (
                debt_plan_id, seq, due_date, total_amount,
                remaining_principal_after, status, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        insert_comp_sql = """
            INSERT INTO installment_components (
                installment_id, component_type_id, amount
            )
            VALUES (?, ?, ?)
        """
        try:
            cursor = conn.execute(
                update_plan_sql,
                (
                    bank_id,
                    plan_kind,
                    name,
                    principal_amount,
                    currency_id,
                    interest_rate,
                    start_date,
                    installment_count,
                    int(is_active),
                    note,
                    source_card_id,
                    source_kmh_id,
                    plan_id,
                ),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Borç planı bulunamadı.")
            conn.execute(soft_delete_comp_sql, (plan_id,))
            conn.execute(soft_delete_inst_sql, (plan_id,))
            for inst in installments:
                inst_cursor = conn.execute(
                    insert_inst_sql,
                    (
                        plan_id,
                        inst["seq"],
                        inst["due_date"],
                        inst["total_amount"],
                        inst.get("remaining_principal_after"),
                        InstallmentStatus.PLANNED,
                        inst.get("note"),
                    ),
                )
                installment_id = int(inst_cursor.lastrowid)
                for comp in inst["components"]:
                    conn.execute(
                        insert_comp_sql,
                        (
                            installment_id,
                            comp["component_type_id"],
                            comp["amount"],
                        ),
                    )
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Borç planı güncellenemedi.")

    def soft_delete_debt_plan(self, plan_id: int, conn: sqlite3.Connection) -> None:
        soft_delete_plan_sql = """
            UPDATE debt_plans
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        soft_delete_inst_sql = """
            UPDATE installments
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE debt_plan_id = ? AND deleted_at IS NULL
        """
        soft_delete_comp_sql = """
            UPDATE installment_components
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE installment_id IN (
                SELECT id FROM installments WHERE debt_plan_id = ?
            )
            AND deleted_at IS NULL
        """
        try:
            cursor = conn.execute(soft_delete_plan_sql, (plan_id,))
            if cursor.rowcount == 0:
                raise NotFoundError("Borç planı bulunamadı.")
            conn.execute(soft_delete_comp_sql, (plan_id,))
            conn.execute(soft_delete_inst_sql, (plan_id,))
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Borç planı silinemedi.")

    def get_plan_totals(self, plan_id: int) -> Dict[str, Any]:
        sql = """
            SELECT
                dp.principal_amount,
                COALESCE(SUM(i.total_amount), 0) AS installment_total_sum,
                COALESCE(SUM(CASE WHEN i.status != ? THEN i.total_amount ELSE 0 END), 0)
                    AS unpaid_total,
                COALESCE(SUM(CASE WHEN i.status = ? THEN i.total_amount ELSE 0 END), 0)
                    AS paid_total,
                COUNT(CASE WHEN i.status != ? THEN 1 END) AS remaining_installment_count,
                MIN(CASE WHEN i.status != ? THEN i.due_date END) AS next_due_date,
                COUNT(CASE WHEN i.status != ? AND i.due_date < date('now') THEN 1 END)
                    AS overdue_count
            FROM debt_plans dp
            LEFT JOIN installments i
                ON i.debt_plan_id = dp.id AND i.deleted_at IS NULL
            WHERE dp.id = ? AND dp.deleted_at IS NULL
            GROUP BY dp.id, dp.principal_amount
        """
        comp_sql = """
            SELECT
                COALESCE(SUM(CASE WHEN ct.nature = 'principal' THEN ic.amount ELSE 0 END), 0)
                    AS principal_component_total,
                COALESCE(SUM(CASE WHEN ct.nature = 'expense' THEN ic.amount ELSE 0 END), 0)
                    AS expense_component_total
            FROM installment_components ic
            INNER JOIN installments i ON i.id = ic.installment_id AND i.deleted_at IS NULL
            INNER JOIN component_types ct ON ct.id = ic.component_type_id AND ct.deleted_at IS NULL
            WHERE i.debt_plan_id = ? AND ic.deleted_at IS NULL
        """
        paid_status = InstallmentStatus.PAID
        try:
            with get_connection() as conn:
                row = conn.execute(
                    sql,
                    (paid_status, paid_status, paid_status, paid_status, paid_status, plan_id),
                ).fetchone()
                if row is None:
                    raise NotFoundError("Borç planı bulunamadı.")
                totals = _row_to_dict(row)
                comp_row = conn.execute(comp_sql, (plan_id,)).fetchone()
                if comp_row:
                    totals.update(_row_to_dict(comp_row))
                return totals
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Plan toplamları okunamadı.")

    def get_unpaid_installments(self, plan_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, debt_plan_id, seq, due_date, total_amount,
                   remaining_principal_after, status, note
            FROM installments
            WHERE debt_plan_id = ? AND deleted_at IS NULL AND status != ?
            ORDER BY due_date, seq
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (plan_id, InstallmentStatus.PAID)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ödenmemiş taksitler okunamadı.")

    def get_next_installment(self, plan_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT id, debt_plan_id, seq, due_date, total_amount,
                   remaining_principal_after, status, note
            FROM installments
            WHERE debt_plan_id = ? AND deleted_at IS NULL AND status != ?
            ORDER BY due_date, seq
            LIMIT 1
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (plan_id, InstallmentStatus.PAID)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Sonraki taksit okunamadı.")

    def get_overdue_installments(self, as_of_date: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                i.id, i.debt_plan_id, i.seq, i.due_date, i.total_amount,
                i.status, dp.name AS plan_name, dp.plan_kind,
                b.name AS bank_name, c.code AS currency_code,
                c.symbol AS currency_symbol, c.scale AS scale
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN banks b ON b.id = dp.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND i.status != ?
              AND i.due_date < ?
              AND dp.is_active = 1
            ORDER BY i.due_date, i.seq
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    sql,
                    (InstallmentStatus.PAID, as_of_date),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Gecikmiş taksitler okunamadı.")

    def get_upcoming_installments(self, limit: int = 10) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                i.id, i.debt_plan_id, i.seq, i.due_date, i.total_amount,
                i.status, dp.name AS plan_name, dp.plan_kind,
                b.name AS bank_name, c.code AS currency_code,
                c.symbol AS currency_symbol, c.scale AS scale
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN banks b ON b.id = dp.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND i.status != ?
              AND dp.is_active = 1
            ORDER BY i.due_date, i.seq
            LIMIT ?
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    sql,
                    (InstallmentStatus.PAID, limit),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Yaklaşan taksitler okunamadı.")

    def get_installments_by_source_card(self, credit_card_id: int) -> List[Dict[str, Any]]:
        """Bir karta bağlı (source_card_id) tüm planların taksitleri.

        Türetilen ekstre, bu taksitleri vade tarihine göre ilgili döneme yerleştirir.
        """
        sql = """
            SELECT
                i.id, i.debt_plan_id, i.seq, i.due_date, i.total_amount,
                i.status, i.paid_date,
                dp.name AS plan_name, dp.plan_kind, dp.installment_count
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND dp.source_card_id = ?
            ORDER BY i.due_date, i.seq
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (credit_card_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Karta bağlı taksitler okunamadı.")

    def get_unpaid_totals_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(i.total_amount), 0) AS unpaid_total
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
              AND i.status != ?
              AND dp.is_active = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            HAVING unpaid_total != 0
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (InstallmentStatus.PAID,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Para birimi bazında borç toplamları okunamadı.")

    def get_installment_with_components(self, installment_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT
                i.id,
                i.debt_plan_id,
                i.seq,
                i.due_date,
                i.total_amount,
                i.remaining_principal_after,
                i.status,
                i.paid_transaction_id,
                i.paid_date,
                i.note,
                dp.name AS plan_name,
                dp.plan_kind,
                dp.bank_id,
                dp.currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale
            FROM installments i
            INNER JOIN debt_plans dp ON dp.id = i.debt_plan_id AND dp.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = dp.currency_id AND c.deleted_at IS NULL
            WHERE i.id = ? AND i.deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (installment_id,)).fetchone()
                if row is None:
                    return None
                installment = _row_to_dict(row)
                installment["components"] = self.get_installment_components(installment_id)
                return installment
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksit okunamadı.")

    def get_installment_detail(self, installment_id: int) -> Optional[Dict[str, Any]]:
        return self.get_installment_with_components(installment_id)

    def mark_installment_paid(
        self,
        installment_id: int,
        transaction_id: int,
        paid_date: str,
        conn: sqlite3.Connection,
    ) -> None:
        sql = """
            UPDATE installments
            SET status = ?, paid_transaction_id = ?, paid_date = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            cursor = conn.execute(
                sql,
                (InstallmentStatus.PAID, transaction_id, paid_date, installment_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Taksit bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksit ödendi olarak işaretlenemedi.")

    def mark_installment_unpaid(
        self,
        installment_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        sql = """
            UPDATE installments
            SET status = ?, paid_transaction_id = NULL, paid_date = NULL
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            cursor = conn.execute(
                sql,
                (InstallmentStatus.PLANNED, installment_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Taksit bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksit planlandı durumuna alınamadı.")

    def get_paid_transaction_id(self, installment_id: int) -> Optional[int]:
        sql = """
            SELECT paid_transaction_id
            FROM installments
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (installment_id,)).fetchone()
                if row is None:
                    return None
                value = row["paid_transaction_id"]
                return int(value) if value is not None else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Taksit ödeme bilgisi okunamadı.")

    def get_paid_installments_by_plan(self, plan_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, debt_plan_id, seq, due_date, total_amount,
                   remaining_principal_after, status, paid_transaction_id,
                   paid_date, note
            FROM installments
            WHERE debt_plan_id = ? AND deleted_at IS NULL AND status = ?
            ORDER BY seq
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (plan_id, InstallmentStatus.PAID)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ödenmiş taksitler okunamadı.")

    def has_paid_installments(self, plan_id: int) -> bool:
        sql = """
            SELECT 1
            FROM installments
            WHERE debt_plan_id = ? AND deleted_at IS NULL AND status = ?
            LIMIT 1
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (plan_id, InstallmentStatus.PAID)).fetchone()
                return row is not None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ödenmiş taksit kontrolü yapılamadı.")
