"""KMH / Ek Hesap iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.account_repository import AccountRepository
from app.repositories.bank_repository import BankRepository
from app.repositories.kmh_repository import KmhRepository
from app.services.audit_service import AuditService


class KmhService:
    """KMH tanımı ve kullanım snapshot yönetimi."""

    def __init__(
        self,
        kmh_repo: Optional[KmhRepository] = None,
        bank_repo: Optional[BankRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._kmh_repo = kmh_repo or KmhRepository()
        self._bank_repo = bank_repo or BankRepository()
        self._account_repo = account_repo or AccountRepository()
        self._audit = audit_service or AuditService()

    def list_kmh_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.list_kmh_accounts(include_inactive=include_inactive)
        return [self.format_kmh_for_ui(row) for row in rows]

    def list_kmh_accounts_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.list_kmh_accounts_by_bank(bank_id, include_inactive)
        return [self.format_kmh_for_ui(row) for row in rows]

    def list_kmh_for_plan(self, bank_id: int, currency_id: int) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.list_kmh_for_plan(bank_id, currency_id)
        return [self.format_kmh_for_ui(row) for row in rows]

    def get_kmh_account(self, kmh_id: int) -> Optional[Dict[str, Any]]:
        row = self._kmh_repo.get_kmh_account_with_details(kmh_id)
        if row is None:
            return None
        return self.format_kmh_for_ui(row)

    def create_kmh_account(self, data: Dict[str, Any]) -> Tuple[int, List[str]]:
        parsed, warnings = self._parse_kmh_data(data)
        try:
            kmh_id = self._kmh_repo.create_kmh_account(
                parsed["bank_id"],
                parsed["account_id"],
                parsed["name"],
                parsed["kmh_limit"],
                parsed["used_amount"],
                parsed["interest_rate"],
                parsed["counts_as_liquidity"],
                parsed["note"],
            )
            self._audit.log_create(
                "kmh_account",
                kmh_id,
                new_value={"name": parsed["name"], "kmh_limit": parsed["kmh_limit"]},
            )
            return kmh_id, warnings
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_kmh_account(self, kmh_id: int, data: Dict[str, Any]) -> List[str]:
        parsed, warnings = self._parse_kmh_data(data, for_update=True)
        is_active = bool(data.get("is_active", True))
        existing = self._kmh_repo.get_kmh_account_with_details(kmh_id)
        try:
            self._kmh_repo.update_kmh_account(
                kmh_id,
                parsed["bank_id"],
                parsed["account_id"],
                parsed["name"],
                parsed["kmh_limit"],
                parsed["used_amount"],
                parsed["interest_rate"],
                parsed["counts_as_liquidity"],
                is_active,
                parsed["note"],
            )
            self._audit.log_update(
                "kmh_account",
                kmh_id,
                old_value={"used_amount": existing.get("used_amount") if existing else None},
                new_value={"used_amount": parsed["used_amount"], "kmh_limit": parsed["kmh_limit"]},
            )
            return warnings
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_kmh_account(self, kmh_id: int) -> None:
        if self._kmh_repo.count_active_plans_by_kmh(kmh_id) > 0:
            raise ValidationError(
                "Bu KMH hesabına bağlı aktif taksitli planlar olduğu için silinemez."
            )
        try:
            existing = self._kmh_repo.get_kmh_account_with_details(kmh_id)
            self._kmh_repo.soft_delete_kmh_account(kmh_id)
            if existing:
                self._audit.log_delete("kmh_account", kmh_id, old_value={"name": existing.get("name")})
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def update_kmh_usage(self, kmh_id: int, used_amount_text: str) -> List[str]:
        kmh = self._kmh_repo.get_kmh_account_with_details(kmh_id)
        if kmh is None:
            raise ValidationError("KMH hesabı bulunamadı.")
        scale = int(kmh["scale"])
        if not is_non_empty_text(used_amount_text):
            used_amount = 0
        else:
            try:
                used_amount = parse_amount(used_amount_text.strip(), scale)
            except ValueError as exc:
                raise ValidationError("Kullanılan tutar için geçersiz format.") from exc
        if used_amount < 0:
            raise ValidationError("Kullanılan tutar negatif olamaz.")
        warnings: List[str] = []
        if used_amount > int(kmh["kmh_limit"]):
            warnings.append(
                "Kullanılan tutar limitten büyük. Limit aşımı durumu oluşmuş olabilir."
            )
        try:
            self._kmh_repo.update_kmh_used_amount(kmh_id, used_amount)
            self._audit.log_update(
                "kmh_account",
                kmh_id,
                old_value={"used_amount": int(kmh["used_amount"])},
                new_value={"used_amount": used_amount},
            )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        return warnings

    def get_kmh_debts_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_debts_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "used_total_display": self._format_amount(
                        int(row["used_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_kmh_available_liquidity_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_available_liquidity_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "available_total_display": self._format_amount(
                        int(row["available_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_kmh_snapshot(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_snapshot()
        return [self.format_kmh_for_ui(row) for row in rows]

    def format_kmh_for_ui(self, kmh: Dict[str, Any]) -> Dict[str, Any]:
        scale = int(kmh["scale"])
        code = kmh["currency_code"]
        symbol = kmh.get("currency_symbol") or ""
        kmh_limit = int(kmh["kmh_limit"])
        used_amount = int(kmh["used_amount"])
        available_amount = int(kmh.get("available_amount", kmh_limit - used_amount))
        return {
            **kmh,
            "kmh_limit_display": self._format_amount(kmh_limit, scale, code, symbol),
            "used_amount_display": self._format_amount(used_amount, scale, code, symbol),
            "available_amount_display": self._format_amount(
                available_amount, scale, code, symbol
            ),
            "available_amount": available_amount,
        }

    def _parse_kmh_data(
        self,
        data: Dict[str, Any],
        for_update: bool = False,
    ) -> Tuple[Dict[str, Any], List[str]]:
        warnings: List[str] = []
        bank_id = data.get("bank_id")
        if bank_id is None:
            raise ValidationError("Banka seçilmeden KMH oluşturulamaz.")
        bank = self._bank_repo.get_bank(int(bank_id))
        if bank is None or not bank.get("is_active"):
            raise ValidationError("Seçilen banka bulunamadı veya aktif değil.")

        account_id = data.get("account_id")
        if account_id is None:
            raise ValidationError("Bağlı hesap seçilmeden KMH oluşturulamaz.")
        account = self._account_repo.get_account_with_currency(int(account_id))
        if account is None or not account.get("is_active"):
            raise ValidationError("Seçilen hesap bulunamadı veya aktif değil.")
        if int(account["bank_id"]) != int(bank_id):
            raise ValidationError("Bağlı hesabın bankası seçilen banka ile aynı olmalı.")

        scale = int(account["currency_scale"])
        name = self._validate_name(str(data.get("name") or ""))

        kmh_limit = self._parse_amount_required(
            str(data.get("kmh_limit_text") or ""),
            scale,
            "KMH limiti",
        )
        if kmh_limit < 0:
            raise ValidationError("KMH limiti negatif olamaz.")

        used_text = str(data.get("used_amount_text") or "").strip()
        if used_text:
            used_amount = self._parse_amount_required(used_text, scale, "Kullanılan tutar")
        else:
            used_amount = 0
        if used_amount < 0:
            raise ValidationError("Kullanılan tutar negatif olamaz.")
        if used_amount > kmh_limit:
            warnings.append(
                "Kullanılan tutar limitten büyük. Limit aşımı durumu oluşmuş olabilir."
            )

        interest_rate = self._parse_interest_rate(data.get("interest_rate"))
        counts_as_liquidity = bool(data.get("counts_as_liquidity", True))
        note = self._normalize_optional_text(data.get("note"))

        return (
            {
                "bank_id": int(bank_id),
                "account_id": int(account_id),
                "name": name,
                "kmh_limit": kmh_limit,
                "used_amount": used_amount,
                "interest_rate": interest_rate,
                "counts_as_liquidity": counts_as_liquidity,
                "note": note,
            },
            warnings,
        )

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
            raise ValidationError("KMH adı boş olamaz.")
        return name.strip()

    def _parse_amount_required(self, text: str, scale: int, label: str) -> int:
        if not is_non_empty_text(text):
            raise ValidationError(f"{label} boş olamaz.")
        try:
            return parse_amount(text.strip(), scale)
        except ValueError as exc:
            raise ValidationError(f"{label} için geçersiz tutar formatı.") from exc

    @staticmethod
    def _parse_interest_rate(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError as exc:
            raise ValidationError("Geçersiz faiz oranı formatı.") from exc

    @staticmethod
    def _normalize_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None
