"""Kredi kartı iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.bank_repository import BankRepository
from app.repositories.credit_card_repository import CreditCardRepository
from app.repositories.currency_repository import CurrencyRepository
from app.services.audit_service import AuditService


class CreditCardService:
    """Kredi kartı tanımı ve ekstre snapshot yönetimi."""

    def __init__(
        self,
        credit_card_repo: Optional[CreditCardRepository] = None,
        bank_repo: Optional[BankRepository] = None,
        currency_repo: Optional[CurrencyRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._credit_card_repo = credit_card_repo or CreditCardRepository()
        self._bank_repo = bank_repo or BankRepository()
        self._currency_repo = currency_repo or CurrencyRepository()
        self._audit = audit_service or AuditService()

    def list_credit_cards(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.list_credit_cards(include_inactive=include_inactive)
        return [self.format_card_for_ui(row) for row in rows]

    def list_credit_cards_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.list_credit_cards_by_bank(bank_id, include_inactive)
        return [self.format_card_for_ui(row) for row in rows]

    def list_credit_cards_for_plan(
        self,
        bank_id: int,
        currency_id: int,
    ) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.list_credit_cards_for_plan(bank_id, currency_id)
        return [self.format_card_for_ui(row) for row in rows]

    def get_credit_card(self, card_id: int) -> Optional[Dict[str, Any]]:
        row = self._credit_card_repo.get_credit_card(card_id)
        if row is None:
            return None
        return self.format_card_for_ui(row)

    def create_credit_card(self, data: Dict[str, Any]) -> int:
        parsed = self._parse_card_data(data)
        try:
            with get_connection() as conn:
                card_id = self._credit_card_repo.create_credit_card(
                    parsed["bank_id"],
                    parsed["name"],
                    parsed["currency_id"],
                    parsed["card_limit"],
                    parsed["statement_day"],
                    parsed["due_day"],
                    parsed["counts_as_liquidity"],
                    parsed["note"],
                    conn,
                )
                self._audit.log_create(
                    "credit_card", card_id, new_value={"name": parsed["name"]}, conn=conn
                )
            return card_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_credit_card(self, card_id: int, data: Dict[str, Any]) -> None:
        parsed = self._parse_card_data(data, for_update=True)
        is_active = bool(data.get("is_active", True))
        existing = self._credit_card_repo.get_credit_card(card_id)
        try:
            with get_connection() as conn:
                self._credit_card_repo.update_credit_card(
                    card_id,
                    parsed["bank_id"],
                    parsed["name"],
                    parsed["currency_id"],
                    parsed["card_limit"],
                    parsed["statement_day"],
                    parsed["due_day"],
                    parsed["counts_as_liquidity"],
                    is_active,
                    parsed["note"],
                    conn,
                )
                if existing:
                    self._audit.log_update(
                        "credit_card",
                        card_id,
                        old_value={"name": existing.get("name")},
                        new_value={"name": parsed["name"]},
                        conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_credit_card(self, card_id: int) -> None:
        if self._credit_card_repo.count_active_statements(card_id) > 0:
            raise ValidationError(
                "Bu karta ait ekstre kayıtları olduğu için kart silinemez. "
                "Önce ekstreleri silin veya kartı pasife alın."
            )
        try:
            existing = self._credit_card_repo.get_credit_card(card_id)
            with get_connection() as conn:
                self._credit_card_repo.soft_delete_credit_card(card_id, conn)
                if existing:
                    self._audit.log_delete(
                        "credit_card", card_id,
                        old_value={"name": existing.get("name")}, conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def list_statements(self, card_id: int) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.list_statements(card_id)
        return [self._format_statement(row) for row in rows]

    def get_statement(self, statement_id: int) -> Optional[Dict[str, Any]]:
        row = self._credit_card_repo.get_statement(statement_id)
        if row is None:
            return None
        return self._format_statement(row)

    def get_latest_statement(self, card_id: int) -> Optional[Dict[str, Any]]:
        row = self._credit_card_repo.get_latest_statement(card_id)
        if row is None:
            return None
        return self._format_statement(row)

    def add_statement(self, data: Dict[str, Any]) -> int:
        parsed = self._parse_statement_data(data)
        card = self._credit_card_repo.get_credit_card(parsed["credit_card_id"])
        if card is None or not card.get("is_active"):
            raise ValidationError("Seçilen kredi kartı bulunamadı veya aktif değil.")
        try:
            with get_connection() as conn:
                statement_id = self._credit_card_repo.create_statement(
                    parsed["credit_card_id"],
                    parsed["statement_date"],
                    parsed["statement_debt"],
                    parsed["min_payment"],
                    parsed["due_date"],
                    parsed["available_limit"],
                    parsed["note"],
                    conn,
                )
                self._audit.log_create(
                    "card_statement",
                    statement_id,
                    new_value={"credit_card_id": parsed["credit_card_id"], "statement_date": parsed["statement_date"]},
                    conn=conn,
                )
            return statement_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_statement(self, statement_id: int, data: Dict[str, Any]) -> None:
        existing = self._credit_card_repo.get_statement(statement_id)
        if existing is None:
            raise ValidationError("Ekstre bulunamadı.")
        data = {**data, "credit_card_id": existing["credit_card_id"]}
        parsed = self._parse_statement_data(data)
        try:
            with get_connection() as conn:
                self._credit_card_repo.update_statement(
                    statement_id,
                    parsed["statement_date"],
                    parsed["statement_debt"],
                    parsed["min_payment"],
                    parsed["due_date"],
                    parsed["available_limit"],
                    parsed["note"],
                    conn,
                )
                self._audit.log_update(
                    "card_statement",
                    statement_id,
                    old_value={"statement_debt": existing.get("statement_debt")},
                    new_value={"statement_debt": parsed["statement_debt"]},
                    conn=conn,
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_statement(self, statement_id: int) -> None:
        existing = self._credit_card_repo.get_statement(statement_id)
        try:
            with get_connection() as conn:
                self._credit_card_repo.soft_delete_statement(statement_id, conn)
                if existing:
                    self._audit.log_delete(
                        "card_statement",
                        statement_id,
                        old_value={"statement_date": existing.get("statement_date")},
                        conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def get_credit_card_debts_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_credit_card_debts_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            formatted.append(
                {
                    **row,
                    "statement_debt_total_display": self._format_amount(
                        int(row["statement_debt_total"]), scale, code, symbol
                    ),
                    "min_payment_total_display": self._format_amount(
                        int(row["min_payment_total"]), scale, code, symbol
                    ),
                }
            )
        return formatted

    def get_total_card_limits_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_total_card_limits_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            formatted.append(
                {
                    **row,
                    "total_limit_display": self._format_amount(
                        int(row["total_limit"]), scale, code, symbol
                    ),
                }
            )
        return formatted

    def get_credit_cards_snapshot(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_credit_cards_snapshot()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            item = {
                **row,
                "card_limit_display": self._format_amount(
                    int(row["card_limit"]), scale, code, symbol
                ),
            }
            if row.get("latest_statement_debt") is not None:
                item["latest_statement_debt_display"] = self._format_amount(
                    int(row["latest_statement_debt"]), scale, code, symbol
                )
            if row.get("latest_min_payment") is not None:
                item["latest_min_payment_display"] = self._format_amount(
                    int(row["latest_min_payment"]), scale, code, symbol
                )
            if row.get("latest_available_limit") is not None:
                item["latest_available_limit_display"] = self._format_amount(
                    int(row["latest_available_limit"]), scale, code, symbol
                )
            formatted.append(item)
        return formatted

    def get_upcoming_card_due_dates(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_upcoming_card_due_dates(limit)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            formatted.append(
                {
                    **row,
                    "min_payment_display": self._format_amount(
                        int(row["min_payment"]), scale, code, symbol
                    ),
                    "statement_debt_display": self._format_amount(
                        int(row["statement_debt"]), scale, code, symbol
                    ),
                }
            )
        return formatted

    def format_card_for_ui(self, card: Dict[str, Any]) -> Dict[str, Any]:
        scale = int(card["scale"])
        code = card["currency_code"]
        symbol = card.get("currency_symbol") or ""
        return {
            **card,
            "card_limit_display": self._format_amount(
                int(card["card_limit"]), scale, code, symbol
            ),
        }

    def _format_statement(self, row: Dict[str, Any]) -> Dict[str, Any]:
        scale = int(row["scale"])
        code = row["currency_code"]
        symbol = row.get("currency_symbol") or ""
        formatted = {
            **row,
            "statement_debt_display": self._format_amount(
                int(row["statement_debt"]), scale, code, symbol
            ),
            "min_payment_display": self._format_amount(
                int(row["min_payment"]), scale, code, symbol
            ),
        }
        if row.get("available_limit") is not None:
            formatted["available_limit_display"] = self._format_amount(
                int(row["available_limit"]), scale, code, symbol
            )
        return formatted

    def _parse_card_data(
        self,
        data: Dict[str, Any],
        for_update: bool = False,
    ) -> Dict[str, Any]:
        bank_id = data.get("bank_id")
        if bank_id is None:
            raise ValidationError("Banka seçilmeden kart oluşturulamaz.")
        bank = self._bank_repo.get_bank(int(bank_id))
        if bank is None or not bank.get("is_active"):
            raise ValidationError("Seçilen banka bulunamadı veya aktif değil.")

        name = self._validate_name(str(data.get("name") or ""))

        currency_id = data.get("currency_id")
        if currency_id is None:
            raise ValidationError("Para birimi seçilmeden kart oluşturulamaz.")
        currency = self._currency_repo.get_currency(int(currency_id))
        if currency is None or not currency.get("is_active"):
            raise ValidationError("Seçilen para birimi bulunamadı veya aktif değil.")
        scale = int(currency["scale"])

        card_limit = self._parse_amount_required(
            str(data.get("card_limit_text") or ""),
            scale,
            "Kart limiti",
        )
        if card_limit < 0:
            raise ValidationError("Kart limiti negatif olamaz.")

        statement_day = self._parse_day(data.get("statement_day"), "Ekstre kesim günü")
        due_day = self._parse_day(data.get("due_day"), "Son ödeme günü")
        counts_as_liquidity = bool(data.get("counts_as_liquidity", False))
        note = self._normalize_optional_text(data.get("note"))

        return {
            "bank_id": int(bank_id),
            "name": name,
            "currency_id": int(currency_id),
            "card_limit": card_limit,
            "statement_day": statement_day,
            "due_day": due_day,
            "counts_as_liquidity": counts_as_liquidity,
            "note": note,
        }

    def _parse_statement_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        credit_card_id = data.get("credit_card_id")
        if credit_card_id is None:
            raise ValidationError("Kredi kartı seçilmeden ekstre eklenemez.")
        card = self._credit_card_repo.get_credit_card(int(credit_card_id))
        if card is None:
            raise ValidationError("Seçilen kredi kartı bulunamadı.")
        scale = int(card["scale"])

        statement_date = str(data.get("statement_date") or "").strip()
        if not statement_date:
            raise ValidationError("Ekstre tarihi zorunludur.")

        statement_debt = self._parse_amount_required(
            str(data.get("statement_debt_text") or ""),
            scale,
            "Ekstre borcu",
        )
        if statement_debt < 0:
            raise ValidationError("Ekstre borcu negatif olamaz.")

        min_payment_text = str(data.get("min_payment_text") or "").strip()
        if min_payment_text:
            min_payment = self._parse_amount_required(min_payment_text, scale, "Asgari ödeme")
        else:
            min_payment = 0
        if min_payment < 0:
            raise ValidationError("Asgari ödeme negatif olamaz.")
        if min_payment > statement_debt:
            raise ValidationError("Asgari ödeme ekstre borcundan büyük olamaz.")

        available_limit = None
        available_text = str(data.get("available_limit_text") or "").strip()
        if available_text:
            available_limit = self._parse_amount_required(
                available_text, scale, "Kullanılabilir limit"
            )

        due_date = self._normalize_optional_text(data.get("due_date"))
        note = self._normalize_optional_text(data.get("note"))

        return {
            "credit_card_id": int(credit_card_id),
            "statement_date": statement_date,
            "statement_debt": statement_debt,
            "min_payment": min_payment,
            "due_date": due_date,
            "available_limit": available_limit,
            "note": note,
        }

    def _format_amount(
        self,
        raw: int,
        scale: int,
        currency_code: str,
        currency_symbol: str,
    ) -> Dict[str, Any]:
        return {
            "raw": raw,
            "display": format_amount_with_grouping(raw, scale),
            "currency_code": currency_code,
            "currency_symbol": currency_symbol,
            "scale": scale,
        }

    @staticmethod
    def _validate_name(name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Kart adı boş olamaz.")
        return name.strip()

    def _parse_amount_required(self, text: str, scale: int, label: str) -> int:
        if not is_non_empty_text(text):
            raise ValidationError(f"{label} boş olamaz.")
        try:
            return parse_amount(text.strip(), scale)
        except ValueError as exc:
            raise ValidationError(f"{label} için geçersiz tutar formatı.") from exc

    @staticmethod
    def _parse_day(value: Any, label: str) -> Optional[int]:
        if value is None or value == "" or value == 0:
            return None
        try:
            day = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{label} geçersiz.") from exc
        if day < 1 or day > 31:
            raise ValidationError(f"{label} 1 ile 31 arasında olmalıdır.")
        return day

    @staticmethod
    def _normalize_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None
