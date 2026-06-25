"""Banka iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.validators import is_non_empty_text
from app.repositories.bank_repository import BankRepository
from app.services.audit_service import AuditService


class BankService:
    """Banka yönetimi."""

    def __init__(
        self,
        bank_repo: Optional[BankRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._bank_repo = bank_repo or BankRepository()
        self._audit = audit_service or AuditService()

    def list_banks(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._bank_repo.list_banks(include_inactive=include_inactive)

    def get_bank(self, bank_id: int) -> Optional[Dict[str, Any]]:
        return self._bank_repo.get_bank(bank_id)

    def create_bank(
        self,
        name: str,
        short_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> int:
        normalized_name = self._validate_name(name)
        normalized_short_name = self._normalize_optional_text(short_name)
        normalized_note = self._normalize_optional_text(note)
        try:
            bank_id = self._bank_repo.create_bank(
                normalized_name,
                normalized_short_name,
                normalized_note,
            )
            self._audit.log_create(
                "bank",
                bank_id,
                new_value={"name": normalized_name, "short_name": normalized_short_name},
            )
            return bank_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_bank(
        self,
        bank_id: int,
        name: str,
        short_name: Optional[str] = None,
        is_active: bool = True,
        note: Optional[str] = None,
    ) -> None:
        normalized_name = self._validate_name(name)
        normalized_short_name = self._normalize_optional_text(short_name)
        normalized_note = self._normalize_optional_text(note)
        existing = self._bank_repo.get_bank(bank_id)
        try:
            self._bank_repo.update_bank(
                bank_id,
                normalized_name,
                normalized_short_name,
                is_active,
                normalized_note,
            )
            if existing:
                self._audit.log_update(
                    "bank",
                    bank_id,
                    old_value=dict(existing),
                    new_value={
                        "name": normalized_name,
                        "short_name": normalized_short_name,
                        "is_active": is_active,
                    },
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_bank(self, bank_id: int) -> None:
        active_accounts = self._bank_repo.count_active_accounts(bank_id)
        if active_accounts > 0:
            raise ValidationError(
                "Bu bankaya bağlı aktif hesaplar olduğu için banka silinemez."
            )
        try:
            existing = self._bank_repo.get_bank(bank_id)
            self._bank_repo.soft_delete_bank(bank_id)
            if existing:
                self._audit.log_delete("bank", bank_id, old_value=dict(existing))
        except NotFoundError as exc:
            raise ValidationError("Silinecek banka bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def _validate_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Banka adı boş olamaz.")
        return name.strip()

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
