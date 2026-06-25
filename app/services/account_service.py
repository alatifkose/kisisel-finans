"""Hesap iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.constants import TrackingMode
from app.core.database import get_connection
from app.core.event_bus import event_bus
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.account_repository import AccountRepository
from app.repositories.bank_repository import BankRepository
from app.repositories.currency_repository import CurrencyRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.audit_service import AuditService

_ZERO_BALANCE_MESSAGE = (
    "Bakiyesi sıfır olmayan hesap pasife alınamaz veya silinemez."
)


class AccountService:
    """Banka hesabı yönetimi."""

    VALID_TRACKING_MODES = {TrackingMode.LEDGER, TrackingMode.SNAPSHOT}

    def __init__(
        self,
        account_repo: Optional[AccountRepository] = None,
        bank_repo: Optional[BankRepository] = None,
        currency_repo: Optional[CurrencyRepository] = None,
        transaction_repo: Optional[TransactionRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._account_repo = account_repo or AccountRepository()
        self._bank_repo = bank_repo or BankRepository()
        self._currency_repo = currency_repo or CurrencyRepository()
        self._transaction_repo = transaction_repo or TransactionRepository()
        self._audit = audit_service or AuditService()

    def list_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._account_repo.list_accounts(include_inactive=include_inactive)

    def list_accounts_by_bank(
        self,
        bank_id: int,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        return self._account_repo.list_accounts_by_bank(
            bank_id,
            include_inactive=include_inactive,
        )

    def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        return self._account_repo.get_account(account_id)

    def create_account(
        self,
        bank_id: int,
        name: str,
        currency_id: int,
        opening_balance_text: str,
        note: Optional[str] = None,
        tracking_mode: str = TrackingMode.LEDGER,
    ) -> int:
        self._ensure_bank_exists(bank_id)
        currency = self._get_currency_or_raise(currency_id)
        normalized_name = self._validate_name(name)
        normalized_tracking_mode = self._validate_tracking_mode(tracking_mode)
        opening_balance = self._parse_balance_text(
            opening_balance_text,
            int(currency["scale"]),
        )
        normalized_note = self._normalize_optional_text(note)
        try:
            with get_connection() as conn:
                account_id = self._account_repo.create_account(
                    bank_id,
                    normalized_name,
                    currency_id,
                    opening_balance,
                    normalized_tracking_mode,
                    normalized_note,
                    conn,
                )
                self._audit.log_create(
                    "account",
                    account_id,
                    new_value={
                        "bank_id": bank_id,
                        "name": normalized_name,
                        "currency_id": currency_id,
                        "opening_balance": opening_balance,
                        "tracking_mode": normalized_tracking_mode,
                    },
                    conn=conn,
                )
            return account_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_account(
        self,
        account_id: int,
        bank_id: int,
        name: str,
        currency_id: int,
        opening_balance_text: str,
        current_balance_text: str,
        tracking_mode: str,
        is_active: bool,
        note: Optional[str] = None,
    ) -> None:
        existing = self._account_repo.get_account(account_id)
        if existing is None:
            raise ValidationError("Hesap bulunamadı.")

        self._ensure_bank_exists(bank_id)
        currency = self._get_currency_or_raise(currency_id)
        normalized_name = self._validate_name(name)
        normalized_tracking_mode = self._validate_tracking_mode(tracking_mode)
        scale = int(currency["scale"])
        opening_balance = self._parse_balance_text(opening_balance_text, scale)
        current_balance = self._parse_balance_text(current_balance_text, scale)

        if not is_active and current_balance != 0:
            raise ValidationError(_ZERO_BALANCE_MESSAGE)

        normalized_note = self._normalize_optional_text(note)
        try:
            with get_connection() as conn:
                self._account_repo.update_account(
                    account_id,
                    bank_id,
                    normalized_name,
                    currency_id,
                    opening_balance,
                    current_balance,
                    normalized_tracking_mode,
                    is_active,
                    normalized_note,
                    conn,
                )
                self._audit.log_update(
                    "account",
                    account_id,
                    old_value=dict(existing),
                    new_value={
                        "bank_id": bank_id,
                        "name": normalized_name,
                        "currency_id": currency_id,
                        "opening_balance": opening_balance,
                        "current_balance": current_balance,
                        "tracking_mode": normalized_tracking_mode,
                        "is_active": is_active,
                    },
                    conn=conn,
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_account(self, account_id: int) -> None:
        account = self._account_repo.get_account(account_id)
        if account is None:
            raise ValidationError("Silinecek hesap bulunamadı.")
        if int(account["current_balance"]) != 0:
            raise ValidationError(_ZERO_BALANCE_MESSAGE)
        try:
            with get_connection() as conn:
                self._account_repo.soft_delete_account(account_id, conn)
                self._audit.log_delete(
                    "account", account_id, old_value=dict(account), conn=conn
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def reconcile_balance(self, account_id: int) -> int:
        """Hareketlerden türetilen bakiyeyi hesapla; current_balance'ı değiştirmez."""
        account = self._account_repo.get_account(account_id)
        if account is None:
            raise ValidationError("Hesap bulunamadı.")

        opening_balance = int(account["opening_balance"])
        in_total, out_total = self._transaction_repo.get_balance_totals_for_account(account_id)
        return opening_balance + in_total - out_total

    def reconcile_all_accounts(self) -> List[Dict[str, Any]]:
        accounts = self._account_repo.list_accounts(include_inactive=False)
        results: List[Dict[str, Any]] = []
        for account in accounts:
            scale = int(account["currency_scale"])
            code = account["currency_code"]
            symbol = account.get("currency_symbol") or ""
            opening = int(account["opening_balance"])
            current = int(account["current_balance"])
            tracking = str(account["tracking_mode"])

            if tracking == TrackingMode.SNAPSHOT:
                results.append(
                    {
                        "account_id": account["id"],
                        "bank_name": account["bank_name"],
                        "account_name": account["name"],
                        "currency_code": code,
                        "currency_symbol": symbol,
                        "scale": scale,
                        "tracking_mode": tracking,
                        "opening_balance": opening,
                        "current_balance": current,
                        "calculated_balance": current,
                        "difference": 0,
                        "status": "snapshot_skipped",
                        "opening_balance_display": self._format_amount(opening, scale, code, symbol),
                        "current_balance_display": self._format_amount(current, scale, code, symbol),
                        "calculated_balance_display": self._format_amount(current, scale, code, symbol),
                        "difference_display": self._format_amount(0, scale, code, symbol),
                    }
                )
                continue

            calculated = self.reconcile_balance(int(account["id"]))
            difference = current - calculated
            status = "ok" if difference == 0 else "drift"
            results.append(
                {
                    "account_id": account["id"],
                    "bank_name": account["bank_name"],
                    "account_name": account["name"],
                    "currency_code": code,
                    "currency_symbol": symbol,
                    "scale": scale,
                    "tracking_mode": tracking,
                    "opening_balance": opening,
                    "current_balance": current,
                    "calculated_balance": calculated,
                    "difference": difference,
                    "status": status,
                    "opening_balance_display": self._format_amount(opening, scale, code, symbol),
                    "current_balance_display": self._format_amount(current, scale, code, symbol),
                    "calculated_balance_display": self._format_amount(calculated, scale, code, symbol),
                    "difference_display": self._format_amount(difference, scale, code, symbol),
                }
            )
        return results

    def fix_account_balance_from_reconcile(self, account_id: int) -> None:
        account = self._account_repo.get_account_with_currency(account_id)
        if account is None:
            raise ValidationError("Hesap bulunamadı.")
        if account["tracking_mode"] != TrackingMode.LEDGER:
            raise ValidationError("Reconcile düzeltmesi yalnızca ledger hesaplarda yapılabilir.")

        calculated = self.reconcile_balance(account_id)
        old_balance = int(account["current_balance"])
        if old_balance == calculated:
            return

        try:
            with get_connection() as conn:
                self._account_repo.set_current_balance(account_id, calculated, conn)
                self._audit.log_update(
                    "account",
                    account_id,
                    old_value={"current_balance": old_balance},
                    new_value={
                        "current_balance": calculated,
                        "reason": "reconcile_fix",
                    },
                    conn=conn,
                )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish("account_balance_changed", {"account_id": account_id})

    def _ensure_bank_exists(self, bank_id: int) -> None:
        if bank_id is None:
            raise ValidationError("Banka seçilmeden hesap oluşturulamaz.")
        bank = self._bank_repo.get_bank(bank_id)
        if bank is None:
            raise ValidationError("Seçilen banka bulunamadı.")

    def _get_currency_or_raise(self, currency_id: int) -> Dict[str, Any]:
        if currency_id is None:
            raise ValidationError("Para birimi seçilmeden hesap oluşturulamaz.")
        currency = self._currency_repo.get_currency(currency_id)
        if currency is None:
            raise ValidationError("Seçilen para birimi bulunamadı.")
        return currency

    def _validate_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Hesap adı boş olamaz.")
        return name.strip()

    def _validate_tracking_mode(self, tracking_mode: str) -> str:
        normalized = (tracking_mode or "").strip().lower()
        if normalized not in self.VALID_TRACKING_MODES:
            raise ValidationError("Takip modu yalnızca ledger veya snapshot olabilir.")
        return normalized

    def _parse_balance_text(self, text: str, scale: int) -> int:
        try:
            return parse_amount(text or "0", scale)
        except ValueError as exc:
            raise ValidationError("Geçersiz tutar formatı.") from exc

    @staticmethod
    def _format_amount(raw: int, scale: int, code: str, symbol: str) -> Dict[str, Any]:
        return {
            "raw": raw,
            "display": format_amount_with_grouping(raw, scale),
            "currency_code": code,
            "currency_symbol": symbol,
            "scale": scale,
        }

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
