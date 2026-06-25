"""KMH / Ek Hesap veri erişimi."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import NotFoundError, RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


_KMH_SELECT = """
    SELECT
        k.id,
        k.bank_id,
        k.account_id,
        k.name,
        k.kmh_limit,
        k.used_amount,
        (k.kmh_limit - k.used_amount) AS available_amount,
        k.interest_rate,
        k.counts_as_liquidity,
        k.is_active,
        k.note,
        k.created_at,
        k.updated_at,
        k.deleted_at,
        b.name AS bank_name,
        a.name AS account_name,
        c.id AS currency_id,
        c.code AS currency_code,
        c.symbol AS currency_symbol,
        c.scale AS scale
    FROM kmh_accounts k
    INNER JOIN banks b ON b.id = k.bank_id AND b.deleted_at IS NULL
    INNER JOIN accounts a ON a.id = k.account_id AND a.deleted_at IS NULL
    INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
    WHERE k.deleted_at IS NULL
"""


class KmhRepository:
    """kmh_accounts tablosu."""

    def list_kmh_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        sql = _KMH_SELECT
        if not include_inactive:
            sql += " AND k.is_active = 1"
        sql += " ORDER BY b.name, k.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH hesapları listelenemedi.")

    def list_kmh_accounts_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        sql = _KMH_SELECT + " AND k.bank_id = ?"
        if not include_inactive:
            sql += " AND k.is_active = 1"
        sql += " ORDER BY k.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (bank_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Banka KMH hesapları listelenemedi.")

    def list_kmh_accounts_by_account(
        self,
        account_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        sql = _KMH_SELECT + " AND k.account_id = ?"
        if not include_inactive:
            sql += " AND k.is_active = 1"
        sql += " ORDER BY k.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (account_id,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Hesap KMH kayıtları listelenemedi.")

    def get_kmh_account(self, kmh_id: int) -> Optional[Dict[str, Any]]:
        sql = _KMH_SELECT + " AND k.id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (kmh_id,)).fetchone()
                return _row_to_dict(row) if row else None
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH hesabı okunamadı.")

    def get_kmh_account_with_details(self, kmh_id: int) -> Optional[Dict[str, Any]]:
        return self.get_kmh_account(kmh_id)

    def create_kmh_account(
        self,
        bank_id: int,
        account_id: int,
        name: str,
        kmh_limit: int,
        used_amount: int,
        interest_rate: Optional[float],
        counts_as_liquidity: bool,
        note: Optional[str],
    ) -> int:
        sql = """
            INSERT INTO kmh_accounts (
                bank_id, account_id, name, kmh_limit, used_amount,
                interest_rate, counts_as_liquidity, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        bank_id,
                        account_id,
                        name,
                        kmh_limit,
                        used_amount,
                        interest_rate,
                        int(counts_as_liquidity),
                        note,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' KMH adı bu bankada zaten kullanılıyor."
            ) from exc
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH hesabı oluşturulamadı.")

    def update_kmh_account(
        self,
        kmh_id: int,
        bank_id: int,
        account_id: int,
        name: str,
        kmh_limit: int,
        used_amount: int,
        interest_rate: Optional[float],
        counts_as_liquidity: bool,
        is_active: bool,
        note: Optional[str],
    ) -> None:
        sql = """
            UPDATE kmh_accounts
            SET bank_id = ?, account_id = ?, name = ?, kmh_limit = ?,
                used_amount = ?, interest_rate = ?, counts_as_liquidity = ?,
                is_active = ?, note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        bank_id,
                        account_id,
                        name,
                        kmh_limit,
                        used_amount,
                        interest_rate,
                        int(counts_as_liquidity),
                        int(is_active),
                        note,
                        kmh_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("KMH hesabı bulunamadı.")
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(
                f"'{name}' KMH adı bu bankada zaten kullanılıyor."
            ) from exc
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH hesabı güncellenemedi.")

    def update_kmh_used_amount(self, kmh_id: int, used_amount: int) -> None:
        sql = """
            UPDATE kmh_accounts
            SET used_amount = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (used_amount, kmh_id))
                if cursor.rowcount == 0:
                    raise NotFoundError("KMH hesabı bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH kullanım tutarı güncellenemedi.")

    def soft_delete_kmh_account(self, kmh_id: int) -> None:
        sql = """
            UPDATE kmh_accounts
            SET deleted_at = CURRENT_TIMESTAMP, is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (kmh_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("KMH hesabı bulunamadı.")
        except NotFoundError:
            raise
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH hesabı silinemedi.")

    def count_active_plans_by_kmh(self, kmh_id: int) -> int:
        sql = """
            SELECT COUNT(*) AS total
            FROM debt_plans
            WHERE source_kmh_id = ?
              AND deleted_at IS NULL
              AND is_active = 1
        """
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (kmh_id,)).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH plan bağlantısı kontrol edilemedi.")

    def get_kmh_debts_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(k.used_amount), 0) AS used_total,
                COUNT(k.id) AS kmh_count
            FROM kmh_accounts k
            INNER JOIN accounts a ON a.id = k.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE k.deleted_at IS NULL AND k.is_active = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            HAVING used_total != 0
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH borç toplamları okunamadı.")

    def get_kmh_available_liquidity_by_currency(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                c.id AS currency_id,
                c.code AS currency_code,
                c.symbol AS currency_symbol,
                c.scale AS scale,
                COALESCE(SUM(k.kmh_limit - k.used_amount), 0) AS available_total,
                COUNT(k.id) AS kmh_count
            FROM kmh_accounts k
            INNER JOIN accounts a ON a.id = k.account_id AND a.deleted_at IS NULL
            INNER JOIN currencies c ON c.id = a.currency_id AND c.deleted_at IS NULL
            WHERE k.deleted_at IS NULL
              AND k.is_active = 1
              AND k.counts_as_liquidity = 1
            GROUP BY c.id, c.code, c.symbol, c.scale
            ORDER BY c.code
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH likidite toplamları okunamadı.")

    def get_kmh_snapshot(self) -> List[Dict[str, Any]]:
        sql = _KMH_SELECT + " ORDER BY b.name, k.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "KMH snapshot okunamadı.")

    def list_kmh_for_plan(
        self,
        bank_id: int,
        currency_id: int,
    ) -> List[Dict[str, Any]]:
        sql = _KMH_SELECT + " AND k.bank_id = ? AND c.id = ? AND k.is_active = 1"
        sql += " ORDER BY k.name"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (bank_id, currency_id)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Plan için KMH hesapları listelenemedi.")
