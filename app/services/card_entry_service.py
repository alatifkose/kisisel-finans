"""Kredi kartı tekil hareket (card_entries) iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.constants import (
    CARD_EXPENSE_ENTRY_TYPES,
    CardEntryType,
    Nature,
    VALID_CARD_ENTRY_TYPES,
)
from app.core.database import get_connection
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.card_entry_repository import CardEntryRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.credit_card_repository import CreditCardRepository
from app.services.audit_service import AuditService


class CardEntryService:
    """Kredi kartı hareketleri: alışveriş / nakit avans / ödeme / ücret / faiz."""

    def __init__(
        self,
        card_entry_repo: Optional[CardEntryRepository] = None,
        credit_card_repo: Optional[CreditCardRepository] = None,
        category_repo: Optional[CategoryRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = card_entry_repo or CardEntryRepository()
        self._credit_card_repo = credit_card_repo or CreditCardRepository()
        self._category_repo = category_repo or CategoryRepository()
        self._audit = audit_service or AuditService()

    def list_entries(self, credit_card_id: int) -> List[Dict[str, Any]]:
        rows = self._repo.list_entries_by_card(credit_card_id)
        return [self.format_entry_for_ui(row) for row in rows]

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        row = self._repo.get_entry(entry_id)
        return self.format_entry_for_ui(row) if row else None

    def get_entry_totals(self, credit_card_id: int) -> Dict[str, int]:
        return self._repo.get_entry_totals_by_card(credit_card_id)

    def create_entry(self, data: Dict[str, Any]) -> int:
        parsed = self._parse_entry_data(data)
        try:
            with get_connection() as conn:
                entry_id = self._repo.create_entry(
                    parsed["credit_card_id"],
                    parsed["txn_date"],
                    parsed["entry_type"],
                    parsed["amount"],
                    parsed["category_id"],
                    parsed["description"],
                    parsed["note"],
                    conn,
                )
                self._audit.log_create(
                    "card_entry",
                    entry_id,
                    new_value={
                        "credit_card_id": parsed["credit_card_id"],
                        "entry_type": parsed["entry_type"],
                        "amount": parsed["amount"],
                    },
                    conn=conn,
                )
            return entry_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_entry(self, entry_id: int, data: Dict[str, Any]) -> None:
        existing = self._repo.get_entry(entry_id)
        if existing is None:
            raise ValidationError("Kart hareketi bulunamadı.")
        # Hareketin kartı değişmez; mevcut karta göre doğrula.
        data = {**data, "credit_card_id": existing["credit_card_id"]}
        parsed = self._parse_entry_data(data)
        try:
            with get_connection() as conn:
                self._repo.update_entry(
                    entry_id,
                    parsed["txn_date"],
                    parsed["entry_type"],
                    parsed["amount"],
                    parsed["category_id"],
                    parsed["description"],
                    parsed["note"],
                    conn,
                )
                self._audit.log_update(
                    "card_entry",
                    entry_id,
                    old_value={
                        "entry_type": existing.get("entry_type"),
                        "amount": existing.get("amount"),
                    },
                    new_value={
                        "entry_type": parsed["entry_type"],
                        "amount": parsed["amount"],
                    },
                    conn=conn,
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_entry(self, entry_id: int) -> None:
        existing = self._repo.get_entry(entry_id)
        try:
            with get_connection() as conn:
                self._repo.soft_delete_entry(entry_id, conn)
                if existing:
                    self._audit.log_delete(
                        "card_entry",
                        entry_id,
                        old_value={
                            "entry_type": existing.get("entry_type"),
                            "amount": existing.get("amount"),
                        },
                        conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError("Silinecek kart hareketi bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def format_entry_for_ui(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        scale = int(entry["scale"])
        return {
            **entry,
            "amount_display": format_amount_with_grouping(int(entry["amount"]), scale),
        }

    def _parse_entry_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        credit_card_id = data.get("credit_card_id")
        if credit_card_id is None:
            raise ValidationError("Kart seçilmeden hareket eklenemez.")
        card = self._credit_card_repo.get_credit_card(int(credit_card_id))
        if card is None or not card.get("is_active"):
            raise ValidationError("Seçilen kart bulunamadı veya aktif değil.")
        scale = int(card["scale"])

        entry_type = str(data.get("entry_type") or "").strip().lower()
        if entry_type not in VALID_CARD_ENTRY_TYPES:
            raise ValidationError("Geçersiz kart hareketi türü.")

        txn_date = str(data.get("txn_date") or "").strip()
        if not is_non_empty_text(txn_date):
            raise ValidationError("Hareket tarihi zorunludur.")

        amount = self._parse_amount_required(
            str(data.get("amount_text") or ""), scale, "Tutar"
        )
        if amount <= 0:
            raise ValidationError("Tutar sıfırdan büyük olmalıdır.")

        category_id = self._validate_category(entry_type, data.get("category_id"))
        description = self._normalize_optional_text(data.get("description"))
        note = self._normalize_optional_text(data.get("note"))

        return {
            "credit_card_id": int(credit_card_id),
            "txn_date": txn_date,
            "entry_type": entry_type,
            "amount": amount,
            "category_id": category_id,
            "description": description,
            "note": note,
        }

    def _validate_category(
        self,
        entry_type: str,
        category_id: Any,
    ) -> Optional[int]:
        if category_id in (None, ""):
            return None
        if entry_type not in CARD_EXPENSE_ENTRY_TYPES:
            raise ValidationError(
                "Yalnızca gider niteliğindeki hareketlere (alışveriş/ücret/faiz) "
                "kategori atanabilir."
            )
        category = self._category_repo.get_category(int(category_id))
        if category is None:
            raise ValidationError("Seçilen kategori bulunamadı.")
        if category["nature"] != Nature.EXPENSE:
            raise ValidationError("Kart gideri için kategori niteliği gider olmalıdır.")
        return int(category_id)

    def _parse_amount_required(self, text: str, scale: int, label: str) -> int:
        if not is_non_empty_text(text):
            raise ValidationError(f"{label} boş olamaz.")
        try:
            return parse_amount(text.strip(), scale)
        except ValueError as exc:
            raise ValidationError(f"{label} için geçersiz tutar formatı.") from exc

    @staticmethod
    def _normalize_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None
