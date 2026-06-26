"""Kredi kartı tekil hareket (card_entries) veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.constants import (
    CARD_CASH_ADVANCE_ENTRY_TYPES,
    CARD_DEBT_DECREASING_ENTRY_TYPES,
    CARD_DEBT_INCREASING_ENTRY_TYPES,
)
from app.core.database import connection_scope, get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


def _sql_set(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


_ENTRY_SELECT = """
    SELECT
        ce.id,
        ce.credit_card_id,
        ce.txn_date,
        ce.entry_type,
        ce.amount,
        ce.category_id,
        ce.description,
        ce.note,
        ce.created_at,
        ce.updated_at,
        ce.deleted_at,
        cat.name AS category_name,
        cc.name AS card_name,
        c.code AS currency_code,
        c.symbol AS currency_symbol,
        c.scale AS scale
    FROM card_entries ce
    INNER JOIN credit_cards cc
        ON cc.id = ce.credit_card_id AND cc.deleted_at IS NULL
    INNER JOIN currencies c
        ON c.id = cc.currency_id AND c.deleted_at IS NULL
    LEFT JOIN categories cat
        ON cat.id = ce.category_id AND cat.deleted_at IS NULL
    WHERE ce.deleted_at IS NULL
"""


class CardEntryRepository:
    """card_entries tablosu CRUD ve toplama işlemleri."""

    def list_entries_by_card(self, credit_card_id: int) -> List[Dict[str, Any]]:
        sql = _ENTRY_SELECT + " AND ce.credit_card_id = ? ORDER BY ce.txn_date, ce.id"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (credit_card_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketleri listelenemedi.")

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        sql = _ENTRY_SELECT + " AND ce.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (entry_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketi okunamadı.")

    def create_entry(
        self,
        credit_card_id: int,
        txn_date: str,
        entry_type: str,
        amount: int,
        category_id: Optional[int],
        description: Optional[str],
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO card_entries (
                credit_card_id, txn_date, entry_type, amount,
                category_id, description, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        credit_card_id,
                        txn_date,
                        entry_type,
                        amount,
                        category_id,
                        description,
                        note,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketi oluşturulamadı.")

    def update_entry(
        self,
        entry_id: int,
        txn_date: str,
        entry_type: str,
        amount: int,
        category_id: Optional[int],
        description: Optional[str],
        note: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE card_entries
            SET txn_date = ?, entry_type = ?, amount = ?, category_id = ?,
                description = ?, note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(
                    sql,
                    (
                        txn_date,
                        entry_type,
                        amount,
                        category_id,
                        description,
                        note,
                        entry_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Kart hareketi bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketi güncellenemedi.")

    def soft_delete_entry(
        self,
        entry_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        sql = """
            UPDATE card_entries
            SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with connection_scope(conn) as c:
                cursor = c.execute(sql, (entry_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Kart hareketi bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketi silinemedi.")

    def get_entry_totals_by_card(self, credit_card_id: int) -> Dict[str, int]:
        """Karta ait tekil hareketlerin özet toplamları (en küçük birim).

        debt = borcu artıranlar − ödemeler
        cash_advance_charged = nakit avans (tek çekim) toplamı
        payments = ödeme toplamı
        """
        inc = _sql_set(CARD_DEBT_INCREASING_ENTRY_TYPES)
        dec = _sql_set(CARD_DEBT_DECREASING_ENTRY_TYPES)
        ca = _sql_set(CARD_CASH_ADVANCE_ENTRY_TYPES)
        sql = f"""
            SELECT
                COALESCE(SUM(CASE WHEN entry_type IN ({inc}) THEN amount ELSE 0 END), 0)
                    AS charges,
                COALESCE(SUM(CASE WHEN entry_type IN ({dec}) THEN amount ELSE 0 END), 0)
                    AS payments,
                COALESCE(SUM(CASE WHEN entry_type IN ({ca}) THEN amount ELSE 0 END), 0)
                    AS cash_advance_charged
            FROM card_entries
            WHERE credit_card_id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (credit_card_id,)).fetchone()
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Kart hareketi toplamları okunamadı.")
        charges = int(row["charges"]) if row else 0
        payments = int(row["payments"]) if row else 0
        cash_advance_charged = int(row["cash_advance_charged"]) if row else 0
        return {
            "charges": charges,
            "payments": payments,
            "debt": charges - payments,
            "cash_advance_charged": cash_advance_charged,
        }
