"""Audit log veri erişimi."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import RepositoryError


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _handle_sqlite_error(exc: sqlite3.Error, message: str) -> None:
    raise RepositoryError(message) from exc


def _serialize_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


class AuditRepository:
    """audit_logs tablosu."""

    def create_log(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: Any = None,
        new_value: Any = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        sql = """
            INSERT INTO audit_logs (entity_type, entity_id, action, old_value, new_value)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            entity_type,
            entity_id,
            action,
            _serialize_value(old_value),
            _serialize_value(new_value),
        )
        try:
            if conn is not None:
                cursor = conn.execute(sql, params)
                return int(cursor.lastrowid)
            with get_connection() as connection:
                cursor = connection.execute(sql, params)
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Audit log yazılamadı.")

    def list_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, entity_type, entity_id, action, old_value, new_value, created_at
            FROM audit_logs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Audit loglar okunamadı.")

    def list_logs_by_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, entity_type, entity_id, action, old_value, new_value, created_at
            FROM audit_logs
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at DESC, id DESC
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (entity_type, entity_id)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Varlık audit logları okunamadı.")

    def list_logs_by_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, entity_type, entity_id, action, old_value, new_value, created_at
            FROM audit_logs
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            ORDER BY created_at DESC, id DESC
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (start_date, end_date)).fetchall()
                return [_row_to_dict(row) for row in rows]
        except sqlite3.Error as exc:
            _handle_sqlite_error(exc, "Tarih aralığı audit logları okunamadı.")
