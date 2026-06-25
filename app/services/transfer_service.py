"""Transfer iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.core.constants import Direction, Nature, SOURCE_TRANSFER, TrackingMode
from app.core.database import get_connection
from app.core.event_bus import event_bus
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.account_repository import AccountRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.transaction_service import TransactionService
from app.services.audit_service import AuditService


class TransferService:
    """Hesaplar arası transfer yönetimi."""

    def __init__(
        self,
        transfer_repo: Optional[TransferRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        transaction_repo: Optional[TransactionRepository] = None,
        transaction_service: Optional[TransactionService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._transfer_repo = transfer_repo or TransferRepository()
        self._account_repo = account_repo or AccountRepository()
        self._transaction_repo = transaction_repo or TransactionRepository()
        self._transaction_service = transaction_service or TransactionService(
            transaction_repo=self._transaction_repo,
            account_repo=self._account_repo,
        )
        self._audit = audit_service or AuditService()

    def list_transfers(self) -> List[Dict[str, Any]]:
        rows = self._transfer_repo.list_transfers()
        return [self.format_transfer_for_ui(row) for row in rows]

    def get_transfer(self, transfer_id: int) -> Optional[Dict[str, Any]]:
        row = self._transfer_repo.get_transfer_with_details(transfer_id)
        if row is None:
            return None
        return self.format_transfer_for_ui(row)

    def list_transfers_by_account(self, account_id: int) -> List[Dict[str, Any]]:
        rows = self._transfer_repo.list_transfers_by_account(account_id)
        return [self.format_transfer_for_ui(row) for row in rows]

    def create_transfer(self, data: Dict[str, Any]) -> int:
        parsed = self._parse_transfer_data(data)
        from_account = parsed["from_account"]
        to_account = parsed["to_account"]

        line_note = parsed["description"]
        out_line = self._transfer_line(parsed["from_amount"], line_note)
        in_line = self._transfer_line(parsed["to_amount"], line_note)

        try:
            with get_connection() as conn:
                transfer_id = self._transfer_repo.create_transfer(
                    parsed["from_account_id"],
                    parsed["to_account_id"],
                    parsed["from_amount"],
                    parsed["from_currency_id"],
                    parsed["to_amount"],
                    parsed["to_currency_id"],
                    parsed["exchange_rate"],
                    parsed["transfer_date"],
                    parsed["description"],
                    conn,
                )

                out_txn_id = self._transaction_service.create_system_transaction(
                    parsed["from_account_id"],
                    parsed["transfer_date"],
                    Direction.OUT,
                    parsed["from_amount"],
                    parsed["description"],
                    True,
                    SOURCE_TRANSFER,
                    transfer_id,
                    [out_line],
                    conn,
                )
                in_txn_id = self._transaction_service.create_system_transaction(
                    parsed["to_account_id"],
                    parsed["transfer_date"],
                    Direction.IN,
                    parsed["to_amount"],
                    parsed["description"],
                    True,
                    SOURCE_TRANSFER,
                    transfer_id,
                    [in_line],
                    conn,
                )

                if from_account["tracking_mode"] == TrackingMode.LEDGER:
                    self._account_repo.adjust_balance(
                        parsed["from_account_id"],
                        -parsed["from_amount"],
                        conn,
                    )
                if to_account["tracking_mode"] == TrackingMode.LEDGER:
                    self._account_repo.adjust_balance(
                        parsed["to_account_id"],
                        parsed["to_amount"],
                        conn,
                    )
                self._audit.log_create(
                    "transfer",
                    transfer_id,
                    new_value={
                        "from_account_id": parsed["from_account_id"],
                        "to_account_id": parsed["to_account_id"],
                        "from_amount": parsed["from_amount"],
                        "to_amount": parsed["to_amount"],
                        "transfer_date": parsed["transfer_date"],
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "transfer_created",
            {
                "transfer_id": transfer_id,
                "from_account_id": parsed["from_account_id"],
                "to_account_id": parsed["to_account_id"],
            },
        )
        event_bus.publish(
            "transaction_created",
            {"transaction_id": out_txn_id, "account_id": parsed["from_account_id"]},
        )
        event_bus.publish(
            "transaction_created",
            {"transaction_id": in_txn_id, "account_id": parsed["to_account_id"]},
        )
        event_bus.publish("account_balance_changed", {"account_id": parsed["from_account_id"]})
        event_bus.publish("account_balance_changed", {"account_id": parsed["to_account_id"]})
        return transfer_id

    def delete_transfer(self, transfer_id: int) -> None:
        transfer = self._transfer_repo.get_transfer_with_details(transfer_id)
        if transfer is None:
            raise ValidationError("Transfer bulunamadı.")

        try:
            with get_connection() as conn:
                txns = self._transaction_repo.list_transactions_by_source(
                    SOURCE_TRANSFER,
                    transfer_id,
                    conn,
                )
                if len(txns) != 2:
                    raise ValidationError(
                        "Bu transfere bağlı para hareketleri tutarsız. "
                        "İşlem otomatik geri alınamaz."
                    )

                for txn in txns:
                    self._transaction_service.reverse_transaction_balance(txn, conn)
                    self._transaction_service.soft_delete_transaction_in_tx(
                        int(txn["id"]),
                        conn,
                    )

                self._transfer_repo.soft_delete_transfer(transfer_id, conn)
                self._audit.log_delete(
                    "transfer",
                    transfer_id,
                    old_value={
                        "from_account_id": transfer["from_account_id"],
                        "to_account_id": transfer["to_account_id"],
                        "from_amount": transfer["from_amount"],
                        "to_amount": transfer["to_amount"],
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "transfer_deleted",
            {
                "transfer_id": transfer_id,
                "from_account_id": transfer["from_account_id"],
                "to_account_id": transfer["to_account_id"],
            },
        )
        event_bus.publish(
            "account_balance_changed",
            {"account_id": transfer["from_account_id"]},
        )
        event_bus.publish(
            "account_balance_changed",
            {"account_id": transfer["to_account_id"]},
        )

    def format_transfer_for_ui(self, transfer: Dict[str, Any]) -> Dict[str, Any]:
        from_scale = int(transfer["from_scale"])
        to_scale = int(transfer["to_scale"])
        from_code = transfer["from_currency_code"]
        to_code = transfer["to_currency_code"]
        from_symbol = transfer.get("from_currency_symbol") or ""
        to_symbol = transfer.get("to_currency_symbol") or ""
        return {
            **transfer,
            "from_amount_display": self._format_amount(
                int(transfer["from_amount"]),
                from_scale,
                from_code,
                from_symbol,
            ),
            "to_amount_display": self._format_amount(
                int(transfer["to_amount"]),
                to_scale,
                to_code,
                to_symbol,
            ),
        }

    def _parse_transfer_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from_account_id = data.get("from_account_id")
        to_account_id = data.get("to_account_id")
        if from_account_id is None:
            raise ValidationError("Kaynak hesap seçilmeden transfer yapılamaz.")
        if to_account_id is None:
            raise ValidationError("Hedef hesap seçilmeden transfer yapılamaz.")
        if int(from_account_id) == int(to_account_id):
            raise ValidationError("Kaynak ve hedef hesap aynı olamaz.")

        from_account = self._get_active_account(int(from_account_id))
        to_account = self._get_active_account(int(to_account_id))

        from_scale = int(from_account["currency_scale"])
        to_scale = int(to_account["currency_scale"])
        from_currency_id = int(from_account["currency_id"])
        to_currency_id = int(to_account["currency_id"])

        from_amount = self._parse_amount_required(
            str(data.get("from_amount_text") or ""),
            from_scale,
            "Kaynak tutar",
        )
        to_amount = self._parse_amount_required(
            str(data.get("to_amount_text") or ""),
            to_scale,
            "Hedef tutar",
        )
        if from_amount <= 0:
            raise ValidationError("Kaynak tutar sıfırdan büyük olmalıdır.")
        if to_amount <= 0:
            raise ValidationError("Hedef tutar sıfırdan büyük olmalıdır.")

        if from_currency_id == to_currency_id and from_amount != to_amount:
            raise ValidationError(
                "Aynı para birimindeki transferlerde kaynak ve hedef tutar eşit olmalıdır."
            )

        transfer_date = self._validate_date(str(data.get("transfer_date") or ""))
        description = self._normalize_optional_text(data.get("description"))
        exchange_rate = self._parse_exchange_rate(data.get("exchange_rate"))

        return {
            "from_account_id": int(from_account_id),
            "to_account_id": int(to_account_id),
            "from_account": from_account,
            "to_account": to_account,
            "from_amount": from_amount,
            "to_amount": to_amount,
            "from_currency_id": from_currency_id,
            "to_currency_id": to_currency_id,
            "exchange_rate": exchange_rate,
            "transfer_date": transfer_date,
            "description": description,
        }

    def _get_active_account(self, account_id: int) -> Dict[str, Any]:
        account = self._account_repo.get_account_with_currency(account_id)
        if account is None:
            raise ValidationError("Seçilen hesap bulunamadı.")
        if not account.get("is_active"):
            raise ValidationError("Seçilen hesap aktif değil.")
        return account

    @staticmethod
    def _transfer_line(amount: int, note: Optional[str]) -> Dict[str, Any]:
        return {
            "nature": Nature.TRANSFER,
            "category_id": None,
            "asset_id": None,
            "amount": amount,
            "note": note,
        }

    @staticmethod
    def _format_amount(
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
    def _parse_amount_required(text: str, scale: int, label: str) -> int:
        if not is_non_empty_text(text):
            raise ValidationError(f"{label} boş olamaz.")
        try:
            return parse_amount(text.strip(), scale)
        except ValueError as exc:
            raise ValidationError(f"{label} için geçersiz tutar formatı.") from exc

    @staticmethod
    def _validate_date(transfer_date: str) -> str:
        if not is_non_empty_text(transfer_date):
            raise ValidationError("Transfer tarihi zorunludur.")
        return transfer_date.strip()

    @staticmethod
    def _parse_exchange_rate(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            rate = float(text.replace(",", "."))
        except ValueError as exc:
            raise ValidationError("Geçersiz kur formatı.") from exc
        if rate <= 0:
            raise ValidationError("Kur değeri pozitif olmalıdır.")
        return rate

    @staticmethod
    def _normalize_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None
