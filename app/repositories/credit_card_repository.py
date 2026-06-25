"""Kredi kartı ve ekstre snapshot veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_CARD_SELECT = """
    SELECT
        cc.id,
        cc.bank_id,
        cc.name,
        cc.currency_id,
        cc.card_limit,
        cc.statement_day,
        cc.due_day,
        cc.counts_as_liquidity,
        cc.is_active,
        cc.note,
        cc.created_at,
        cc.updated_at,
        cc.deleted_at,
        b.name AS bank_name,
        c.code AS currency_code,
        c.symbol AS currency_symbol,
        c.scale AS scale
    FROM credit_cards cc
    INNER JOIN banks b ON b.id = cc.bank_id AND b.deleted_at IS NULL
    INNER JOIN currencies c ON c.id = cc.currency_id AND c.deleted_at IS NULL
    WHERE cc.deleted_at IS NULL
"""


class CreditCardRepository:
    """credit_cards ve card_statements tabloları."""

    def list_credit_cards(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = _CARD_SELECT
        if not include_inactive:
            sql += " AND cc.is_active = 1"
        sql += " ORDER BY b.name, cc.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartları listelenemedi.")

    def list_credit_cards_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        sql = _CARD_SELECT + " AND cc.bank_id = ?"
        if not include_inactive:
            sql += " AND cc.is_active = 1"
        sql += " ORDER BY cc.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (bank_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka kredi kartları listelenemedi.")

    def get_credit_card(self, card_id: int) -> Optional[Dict[str, Any]]:
        sql = _CARD_SELECT + " AND cc.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (card_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı okunamadı.")

    def get_credit_card_with_bank(self, card_id: int) -> Optional[Dict[str, Any]]:
        return self.get_credit_card(card_id)

    def create_credit_card(
        self,
        bank_id: int,
        name: str,
        currency_id: int,
        card_limit: int,
        statement_day: Optional[int],
        due_day: Optional[int],
        counts_as_liquidity: bool,
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO credit_cards (
                bank_id, name, currency_id, card_limit,
                statement_day, due_day, counts_as_liquidity, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        bank_id,
                        name,
                        currency_id,
                        card_limit,
                        statement_day,
                        due_day,
                        int(counts_as_liquidity),
                        note,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' kart adı bu bankada zaten kullanılıyor."
            ) from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı oluşturulamadı.")

    def update_credit_card(
        self,
        card_id: int,
        bank_id: int,
        name: str,
        currency_id: int,
        card_limit: int,
        statement_day: Optional[int],
        due_day: Optional[int],
        counts_as_liquidity: bool,
        is_active: bool,
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE credit_cards
            SET bank_id = ?, name = ?, currency_id = ?, card_limit = ?,
                statement_day = ?, due_day = ?, counts_as_liquidity = ?,
                is_active = ?, note = ?, updated_at = CURRENT_TIMESTAMP
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
                        card_limit,
                        statement_day,
                        due_day,
                        int(counts_as_liquidity),
                        int(is_active),
                        note,
                        card_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Kredi kartı bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' kart adı bu bankada zaten kullanılıyor."
            ) from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı güncellenemedi.")

    def soft_delete_credit_card(
        self,
        card_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE credit_cards
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (card_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Kredi kartı bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı silinemedi.")

    def count_active_statements(self, card_id: int) -> int:
        sql = """
            SELECT COUNT(*) AS total
            FROM card_statements
            WHERE credit_card_id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (card_id,)).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstre sayısı okunamadı.")

    def list_statements(self, card_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                cs.id,
                cs.credit_card_id,
                cs.statement_date,
                cs.statement_debt,
                cs.min_payment,
                cs.due_date,
                cs.available_limit,
                cs.note,
                cs.created_at,
                cs.deleted_at,
                cc.currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale
            FROM card_statements cs
            INNER JOIN credit_cards cc
                ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.credit_card_id = ? AND cs.deleted_at IS NULL
            ORDER BY cs.statement_date DESC, cs.id DESC
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (card_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstreler listelenemedi.")

    def get_statement(self, statement_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT
                cs.id,
                cs.credit_card_id,
                cs.statement_date,
                cs.statement_debt,
                cs.min_payment,
                cs.due_date,
                cs.available_limit,
                cs.note,
                cs.created_at,
                cs.deleted_at,
                cc.currency_id,
                cc.name AS card_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale
            FROM card_statements cs
            INNER JOIN credit_cards cc
                ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.id = ? AND cs.deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (statement_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstre okunamadı.")

    def get_latest_statement(self, card_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT
                cs.id,
                cs.credit_card_id,
                cs.statement_date,
                cs.statement_debt,
                cs.min_payment,
                cs.due_date,
                cs.available_limit,
                cs.note,
                cs.created_at,
                cc.currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale
            FROM card_statements cs
            INNER JOIN credit_cards cc
                ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL
            INNER JOIN currencies c
                ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.credit_card_id = ? AND cs.deleted_at IS NULL
            ORDER BY cs.statement_date DESC, cs.id DESC
            LIMIT 1
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (card_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Son ekstre okunamadı.")

    def create_statement(
        self,
        credit_card_id: int,
        statement_date: str,
        statement_debt: int,
        min_payment: int,
        due_date: Optional[str],
        available_limit: Optional[int],
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO card_statements (
                credit_card_id, statement_date, statement_debt,
                min_payment, due_date, available_limit, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        credit_card_id,
                        statement_date,
                        statement_debt,
                        min_payment,
                        due_date,
                        available_limit,
                        note,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                "Bu kart için aynı ekstre tarihi zaten kayıtlı."
            ) from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstre oluşturulamadı.")

    def update_statement(
        self,
        statement_id: int,
        statement_date: str,
        statement_debt: int,
        min_payment: int,
        due_date: Optional[str],
        available_limit: Optional[int],
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE card_statements
            SET statement_date = ?, statement_debt = ?, min_payment = ?,
                due_date = ?, available_limit = ?, note = ?
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        statement_date,
                        statement_debt,
                        min_payment,
                        due_date,
                        available_limit,
                        note,
                        statement_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Ekstre bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                "Bu kart için aynı ekstre tarihi zaten kayıtlı."
            ) from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstre güncellenemedi.")

    def soft_delete_statement(
        self,
        statement_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE card_statements
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (statement_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Ekstre bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Ekstre silinemedi.")

    def get_credit_card_debts_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(latest.statement_debt), 0) AS statement_debt_total,
                COALESCE(SUM(latest.min_payment), 0) AS min_payment_total,
                COUNT(latest.credit_card_id) AS card_count
            FROM credit_cards cc
            INNER JOIN currencies c
                ON c.id = cc.currency_id AND c.deleted_at IS NULL
            LEFT JOIN (
                SELECT cs.credit_card_id, cs.statement_debt, cs.min_payment
                FROM card_statements cs
                INNER JOIN (
                    SELECT credit_card_id, MAX(statement_date) AS max_date
                    FROM card_statements
                    WHERE deleted_at IS NULL
                    GROUP BY credit_card_id
                ) mx ON mx.credit_card_id = cs.credit_card_id
                    AND mx.max_date = cs.statement_date
                WHERE cs.deleted_at IS NULL
            ) latest ON latest.credit_card_id = cc.id
            WHERE cc.deleted_at IS NULL AND cc.is_active = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            HAVING statement_debt_total != 0 OR card_count > 0
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı borç toplamları okunamadı.")

    def get_total_card_limits_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(cc.card_limit), 0) AS total_limit,
                COUNT(cc.id) AS card_count
            FROM credit_cards cc
            INNER JOIN currencies c
                ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cc.deleted_at IS NULL AND cc.is_active = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart limit toplamları okunamadı.")

    def get_credit_cards_snapshot(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                cc.id,
                b.name AS bank_name,
                cc.name AS card_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                cc.card_limit,
                cc.statement_day,
                cc.due_day,
                cc.counts_as_liquidity,
                cc.is_active,
                latest.statement_date AS latest_statement_date,
                latest.statement_debt AS latest_statement_debt,
                latest.min_payment AS latest_min_payment,
                latest.due_date AS latest_due_date,
                latest.available_limit AS latest_available_limit
            FROM credit_cards cc
            INNER JOIN banks b ON b.id = cc.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = cc.currency_id AND c.deleted_at IS NULL
            LEFT JOIN (
                SELECT cs.*
                FROM card_statements cs
                INNER JOIN (
                    SELECT credit_card_id, MAX(statement_date) AS max_date
                    FROM card_statements
                    WHERE deleted_at IS NULL
                    GROUP BY credit_card_id
                ) mx ON mx.credit_card_id = cs.credit_card_id
                    AND mx.max_date = cs.statement_date
                WHERE cs.deleted_at IS NULL
            ) latest ON latest.credit_card_id = cc.id
            WHERE cc.deleted_at IS NULL
            ORDER BY b.name, cc.name
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kredi kartı snapshot okunamadı.")

    def get_upcoming_card_due_dates(self, limit: int = 5) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                cs.due_date,
                cs.min_payment,
                cs.statement_debt,
                cc.id AS credit_card_id,
                cc.name AS card_name,
                b.name AS bank_name,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale
            FROM card_statements cs
            INNER JOIN (
                SELECT credit_card_id, MAX(statement_date) AS max_date
                FROM card_statements
                WHERE deleted_at IS NULL
                GROUP BY credit_card_id
            ) mx ON mx.credit_card_id = cs.credit_card_id
                AND mx.max_date = cs.statement_date
            INNER JOIN credit_cards cc
                ON cc.id = cs.credit_card_id AND cc.deleted_at IS NULL AND cc.is_active = 1
            INNER JOIN banks b ON b.id = cc.bank_id AND b.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = cc.currency_id AND c.deleted_at IS NULL
            WHERE cs.deleted_at IS NULL
              AND cs.due_date IS NOT NULL
              AND cs.due_date >= date('now')
            ORDER BY cs.due_date, cc.name
            LIMIT ?
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Yaklaşan kart ödemeleri okunamadı.")

    def list_credit_cards_for_plan(
        self,
        bank_id: int,
        currency_id: int,
    ) -> List[Dict[str, Any]]:
        sql = _CARD_SELECT + " AND cc.bank_id = ? AND cc.currency_id = ? AND cc.is_active = 1"
        sql += " ORDER BY cc.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (bank_id, currency_id)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Plan için kredi kartları listelenemedi.")
