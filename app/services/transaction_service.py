"""Para hareketi iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.constants import (
    Direction,
    Nature,
    SOURCE_INSTALLMENT,
    SOURCE_MANUAL,
    SOURCE_TRANSFER,
    TrackingMode,
    VALID_MANUAL_TRANSACTION_NATURES,
)
from app.core.database import get_connection
from app.core.event_bus import event_bus
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.account_repository import AccountRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.audit_service import AuditService


class TransactionService:
    """Gelir, gider ve masraf işlemleri."""

    VALID_DIRECTIONS = {Direction.IN, Direction.OUT}

    def __init__(
        self,
        transaction_repo: Optional[TransactionRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        category_repo: Optional[CategoryRepository] = None,
        asset_repo: Optional[AssetRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._transaction_repo = transaction_repo or TransactionRepository()
        self._account_repo = account_repo or AccountRepository()
        self._category_repo = category_repo or CategoryRepository()
        self._asset_repo = asset_repo or AssetRepository()
        self._audit = audit_service or AuditService()

    def list_transactions(self) -> List[Dict[str, Any]]:
        return self._transaction_repo.list_transactions()

    def list_transactions_by_account(self, account_id: int) -> List[Dict[str, Any]]:
        return self._transaction_repo.list_transactions_by_account(account_id)

    def get_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        return self._transaction_repo.get_transaction_with_lines(transaction_id)

    def create_transaction(
        self,
        account_id: int,
        txn_date: str,
        direction: str,
        total_amount_text: str,
        description: Optional[str],
        affects_balance: bool,
        lines: List[Dict[str, Any]],
    ) -> int:
        account = self._get_account_or_raise(account_id)
        scale = int(account["currency_scale"])
        normalized_direction = self._validate_direction(direction)
        normalized_date = self._validate_date(txn_date)
        total_amount = self._parse_amount_text(total_amount_text, scale)
        parsed_lines = self._validate_and_parse_lines(
            lines,
            scale,
            normalized_direction,
            total_amount,
        )
        normalized_description = self._normalize_optional_text(description)

        try:
            with get_connection() as conn:
                transaction_id = self._transaction_repo.create_transaction_with_lines(
                    account_id,
                    normalized_date,
                    normalized_direction,
                    total_amount,
                    normalized_description,
                    affects_balance,
                    SOURCE_MANUAL,
                    None,
                    parsed_lines,
                    conn,
                )
                if affects_balance and account["tracking_mode"] == TrackingMode.LEDGER:
                    delta = self._balance_delta(normalized_direction, total_amount)
                    self._account_repo.adjust_balance(account_id, delta, conn)
                self._audit.log_create(
                    "transaction",
                    transaction_id,
                    new_value={
                        "account_id": account_id,
                        "txn_date": normalized_date,
                        "direction": normalized_direction,
                        "total_amount": total_amount,
                        "source_type": SOURCE_MANUAL,
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish("transaction_created", {"transaction_id": transaction_id, "account_id": account_id})
        event_bus.publish("account_balance_changed", {"account_id": account_id})
        return transaction_id

    def update_transaction(
        self,
        transaction_id: int,
        account_id: int,
        txn_date: str,
        direction: str,
        total_amount_text: str,
        description: Optional[str],
        affects_balance: bool,
        lines: List[Dict[str, Any]],
    ) -> None:
        old_txn = self._transaction_repo.get_transaction_with_lines(transaction_id)
        if old_txn is None:
            raise ValidationError("İşlem bulunamadı.")
        self._ensure_manual_editable(old_txn)

        old_account = self._get_account_or_raise(int(old_txn["account_id"]))
        new_account = self._get_account_or_raise(account_id)
        scale = int(new_account["currency_scale"])
        normalized_direction = self._validate_direction(direction)
        normalized_date = self._validate_date(txn_date)
        total_amount = self._parse_amount_text(total_amount_text, scale)
        parsed_lines = self._validate_and_parse_lines(
            lines,
            scale,
            normalized_direction,
            total_amount,
        )
        normalized_description = self._normalize_optional_text(description)

        try:
            with get_connection() as conn:
                self._reverse_balance_effect(old_txn, old_account, conn)
                self._transaction_repo.update_transaction_with_lines(
                    transaction_id,
                    account_id,
                    normalized_date,
                    normalized_direction,
                    total_amount,
                    normalized_description,
                    affects_balance,
                    parsed_lines,
                    conn,
                )
                if affects_balance and new_account["tracking_mode"] == TrackingMode.LEDGER:
                    delta = self._balance_delta(normalized_direction, total_amount)
                    self._account_repo.adjust_balance(account_id, delta, conn)
                self._audit.log_update(
                    "transaction",
                    transaction_id,
                    old_value={
                        "account_id": old_txn["account_id"],
                        "total_amount": old_txn["total_amount"],
                        "direction": old_txn["direction"],
                    },
                    new_value={
                        "account_id": account_id,
                        "total_amount": total_amount,
                        "direction": normalized_direction,
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "transaction_updated",
            {
                "transaction_id": transaction_id,
                "account_id": account_id,
                "old_account_id": old_txn["account_id"],
            },
        )
        event_bus.publish("account_balance_changed", {"account_id": old_txn["account_id"]})
        if account_id != old_txn["account_id"]:
            event_bus.publish("account_balance_changed", {"account_id": account_id})

    def delete_transaction(self, transaction_id: int) -> None:
        old_txn = self._transaction_repo.get_transaction_with_lines(transaction_id)
        if old_txn is None:
            raise ValidationError("Silinecek işlem bulunamadı.")
        self._ensure_manual_deletable(old_txn)
        account = self._get_account_or_raise(int(old_txn["account_id"]))

        try:
            with get_connection() as conn:
                self._reverse_balance_effect(old_txn, account, conn)
                self._transaction_repo.soft_delete_transaction(transaction_id, conn)
                self._audit.log_delete(
                    "transaction",
                    transaction_id,
                    old_value={
                        "account_id": old_txn["account_id"],
                        "total_amount": old_txn["total_amount"],
                        "direction": old_txn["direction"],
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "transaction_deleted",
            {"transaction_id": transaction_id, "account_id": old_txn["account_id"]},
        )
        event_bus.publish("account_balance_changed", {"account_id": old_txn["account_id"]})

    def create_system_transaction(
        self,
        account_id: int,
        txn_date: str,
        direction: str,
        total_amount: int,
        description: Optional[str],
        affects_balance: bool,
        source_type: str,
        source_id: Optional[int],
        lines: List[Dict[str, Any]],
        conn,
    ) -> int:
        """Sistem kaynaklı işlem oluşturur; conn zorunludur."""
        account = self._get_account_or_raise(account_id, conn)
        normalized_direction = self._validate_direction(direction)
        normalized_date = self._validate_date(txn_date)
        if total_amount <= 0:
            raise ValidationError("İşlem tutarı sıfırdan büyük olmalıdır.")
        parsed_lines = self._validate_system_lines(
            lines,
            normalized_direction,
            total_amount,
            source_type,
        )
        normalized_description = self._normalize_optional_text(description)

        try:
            return self._transaction_repo.create_transaction_with_lines(
                account_id,
                normalized_date,
                normalized_direction,
                total_amount,
                normalized_description,
                affects_balance,
                source_type,
                source_id,
                parsed_lines,
                conn,
            )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def reverse_transaction_balance(self, txn: Dict[str, Any], conn) -> None:
        account = self._get_account_or_raise(int(txn["account_id"]), conn)
        self._reverse_balance_effect(txn, account, conn)

    def soft_delete_transaction_in_tx(self, transaction_id: int, conn) -> None:
        try:
            self._transaction_repo.soft_delete_transaction(transaction_id, conn)
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

    @staticmethod
    def _ensure_manual_editable(txn: Dict[str, Any]) -> None:
        source = txn.get("source_type")
        if source == SOURCE_INSTALLMENT:
            raise ValidationError(
                "Taksit ödemesinden oluşan işlem buradan düzenlenemez. "
                "İlgili taksitten ödemeyi geri alın."
            )
        if source == SOURCE_TRANSFER:
            raise ValidationError(
                "Transferden oluşan işlem buradan düzenlenemez. "
                "Transferler sayfasından transferi geri alın."
            )

    @staticmethod
    def _ensure_manual_deletable(txn: Dict[str, Any]) -> None:
        source = txn.get("source_type")
        if source == SOURCE_INSTALLMENT:
            raise ValidationError(
                "Bu işlem taksit ödemesine bağlı. "
                "Silmek için ilgili taksitte Ödemeyi Geri Al kullanın."
            )
        if source == SOURCE_TRANSFER:
            raise ValidationError(
                "Transferden oluşan işlem buradan silinemez. "
                "Transferler sayfasından transferi geri alın."
            )

    def _validate_system_lines(
        self,
        lines: List[Dict[str, Any]],
        direction: str,
        total_amount: int,
        source_type: str,
    ) -> List[Dict[str, Any]]:
        if not lines:
            raise ValidationError("İşlem en az bir satır içermelidir.")

        parsed_lines: List[Dict[str, Any]] = []
        line_total = 0

        for line in lines:
            nature = str(line.get("nature") or "").strip().lower()
            amount = int(line["amount"])
            if amount < 0:
                raise ValidationError("Satır tutarı negatif olamaz.")

            if source_type == SOURCE_INSTALLMENT:
                if nature == Nature.PRINCIPAL:
                    if line.get("category_id") is not None:
                        raise ValidationError("Anapara satırında kategori olamaz.")
                    if direction != Direction.OUT:
                        raise ValidationError("Taksit ödemesi çıkış işlemi olmalıdır.")
                elif nature == Nature.EXPENSE:
                    category_id = line.get("category_id")
                    if category_id is None:
                        raise ValidationError("Gider satırı için kategori zorunludur.")
                    category = self._category_repo.get_category(int(category_id))
                    if category is None:
                        raise ValidationError("Seçilen kategori bulunamadı.")
                    if category["nature"] != Nature.EXPENSE:
                        raise ValidationError("Gider satırı için kategori niteliği gider olmalıdır.")
                else:
                    raise ValidationError(
                        "Taksit ödemesinde yalnızca anapara veya gider satırı kullanılabilir."
                    )
            elif source_type == SOURCE_TRANSFER:
                if nature != Nature.TRANSFER:
                    raise ValidationError("Transfer işleminde satır niteliği transfer olmalıdır.")
                if line.get("category_id") is not None:
                    raise ValidationError("Transfer satırında kategori olamaz.")
                if line.get("asset_id") is not None:
                    raise ValidationError("Transfer satırında varlık olamaz.")
                if direction == Direction.IN and nature != Nature.TRANSFER:
                    raise ValidationError("Transfer giriş işlemi geçersiz.")
                if direction == Direction.OUT and nature != Nature.TRANSFER:
                    raise ValidationError("Transfer çıkış işlemi geçersiz.")
            else:
                raise ValidationError("Desteklenmeyen sistem işlem kaynağı.")

            line_total += amount
            parsed_lines.append(
                {
                    "nature": nature,
                    "category_id": line.get("category_id"),
                    "asset_id": line.get("asset_id"),
                    "amount": amount,
                    "note": self._normalize_optional_text(line.get("note")),
                }
            )

        if line_total != total_amount:
            raise ValidationError("Satır toplamı toplam tutara eşit olmalıdır.")

        return parsed_lines

    def _reverse_balance_effect(
        self,
        txn: Dict[str, Any],
        account: Dict[str, Any],
        conn,
    ) -> None:
        if not bool(txn["affects_balance"]):
            return
        if account["tracking_mode"] != TrackingMode.LEDGER:
            return
        delta = self._balance_delta(str(txn["direction"]), int(txn["total_amount"]))
        self._account_repo.adjust_balance(int(txn["account_id"]), -delta, conn)

    @staticmethod
    def _balance_delta(direction: str, amount: int) -> int:
        return amount if direction == Direction.IN else -amount

    def _validate_and_parse_lines(
        self,
        lines: List[Dict[str, Any]],
        scale: int,
        direction: str,
        total_amount: int,
    ) -> List[Dict[str, Any]]:
        if not lines:
            raise ValidationError("İşlem en az bir satır içermelidir.")

        parsed_lines: List[Dict[str, Any]] = []
        line_total = 0

        for line in lines:
            nature = str(line.get("nature") or "").strip().lower()
            if nature not in VALID_MANUAL_TRANSACTION_NATURES:
                raise ValidationError(
                    "Manuel işlem satırında yalnızca gelir, gider veya masraf seçilebilir."
                )
            if direction == Direction.IN and nature != Nature.INCOME:
                raise ValidationError("Giriş işlemlerinde satır niteliği yalnızca gelir olabilir.")
            if direction == Direction.OUT and nature not in {Nature.EXPENSE, Nature.COST}:
                raise ValidationError(
                    "Çıkış işlemlerinde satır niteliği gider veya masraf olabilir."
                )

            category_id = line.get("category_id")
            if category_id is None:
                raise ValidationError("Her işlem satırı için kategori seçilmelidir.")
            category = self._category_repo.get_category(int(category_id))
            if category is None:
                raise ValidationError("Seçilen kategori bulunamadı.")
            if category["nature"] != nature:
                raise ValidationError("Kategori niteliği satır niteliği ile uyuşmuyor.")

            asset_id = line.get("asset_id")
            if asset_id is not None:
                asset = self._asset_repo.get_asset(int(asset_id))
                if asset is None:
                    raise ValidationError("Seçilen varlık bulunamadı.")

            amount_text = line.get("amount_text")
            if not is_non_empty_text(str(amount_text or "")):
                raise ValidationError("Satır tutarı boş olamaz.")
            amount = self._parse_amount_text(str(amount_text), scale)
            line_total += amount

            parsed_lines.append(
                {
                    "nature": nature,
                    "category_id": int(category_id),
                    "asset_id": int(asset_id) if asset_id is not None else None,
                    "amount": amount,
                    "note": self._normalize_optional_text(line.get("note")),
                }
            )

        if line_total != total_amount:
            raise ValidationError("Satır toplamı toplam tutara eşit olmalıdır.")

        return parsed_lines

    def _get_account_or_raise(
        self,
        account_id: int,
        conn=None,
    ) -> Dict[str, Any]:
        if account_id is None:
            raise ValidationError("Hesap seçilmeden işlem oluşturulamaz.")
        account = self._account_repo.get_account_with_currency(account_id, conn)
        if account is None:
            raise ValidationError("Seçilen hesap bulunamadı.")
        return account

    def _validate_direction(self, direction: str) -> str:
        normalized = (direction or "").strip().lower()
        if normalized not in self.VALID_DIRECTIONS:
            raise ValidationError('Yön yalnızca "in" veya "out" olabilir.')
        return normalized

    def _validate_date(self, txn_date: str) -> str:
        if not is_non_empty_text(txn_date):
            raise ValidationError("İşlem tarihi zorunludur.")
        return txn_date.strip()

    def _parse_amount_text(self, text: str, scale: int) -> int:
        if not is_non_empty_text(text):
            raise ValidationError("Toplam tutar boş olamaz.")
        try:
            return parse_amount(text.strip(), scale)
        except ValueError as exc:
            raise ValidationError("Geçersiz tutar formatı.") from exc

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
