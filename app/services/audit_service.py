"""Audit log iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import RepositoryError
from app.repositories.audit_repository import AuditRepository


class AuditService:
    """Değişiklik izleme kayıtları."""

    def __init__(self, audit_repo: Optional[AuditRepository] = None) -> None:
        self._audit_repo = audit_repo or AuditRepository()

    def log_create(
        self,
        entity_type: str,
        entity_id: int,
        new_value: Any = None,
        conn=None,
    ) -> None:
        self._write_log(entity_type, entity_id, "create", None, new_value, conn)

    def log_update(
        self,
        entity_type: str,
        entity_id: int,
        old_value: Any = None,
        new_value: Any = None,
        conn=None,
    ) -> None:
        self._write_log(entity_type, entity_id, "update", old_value, new_value, conn)

    def log_delete(
        self,
        entity_type: str,
        entity_id: int,
        old_value: Any = None,
        conn=None,
    ) -> None:
        self._write_log(entity_type, entity_id, "delete", old_value, None, conn)

    def list_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._audit_repo.list_logs(limit)
        return [self.format_log_for_ui(row) for row in rows]

    def list_logs_by_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[Dict[str, Any]]:
        rows = self._audit_repo.list_logs_by_entity(entity_type, entity_id)
        return [self.format_log_for_ui(row) for row in rows]

    def format_log_for_ui(self, log: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **log,
            "old_value_display": str(log.get("old_value") or "—"),
            "new_value_display": str(log.get("new_value") or "—"),
        }

    def _write_log(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: Any,
        new_value: Any,
        conn,
    ) -> None:
        try:
            self._audit_repo.create_log(
                entity_type,
                entity_id,
                action,
                old_value,
                new_value,
                conn,
            )
        except RepositoryError as exc:
            raise RepositoryError(str(exc)) from exc
