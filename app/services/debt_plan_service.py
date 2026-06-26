"""Borç planı iş mantığı."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set

from app.core.constants import (
    CARD_SOURCE_PLAN_KINDS,
    InstallmentStatus,
    Nature,
    PlanKind,
    SOURCE_INSTALLMENT,
    TrackingMode,
    VALID_COMPONENT_NATURES,
    VALID_PLAN_KINDS,
)
from app.core.database import get_connection
from app.core.event_bus import event_bus
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.money import format_amount, format_amount_with_grouping, parse_amount
from app.core.validators import is_non_empty_text
from app.repositories.account_repository import AccountRepository
from app.repositories.bank_repository import BankRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.component_type_repository import ComponentTypeRepository
from app.repositories.credit_card_repository import CreditCardRepository
from app.repositories.currency_repository import CurrencyRepository
from app.repositories.debt_plan_repository import DebtPlanRepository
from app.repositories.kmh_repository import KmhRepository
from app.services.transaction_service import TransactionService
from app.services.audit_service import AuditService


CATEGORY_MISSING_MESSAGE = (
    "Bu bileşen için gider kategorisi belirlenmemiş. "
    "Tanımlar > Taksit Bileşen Tipleri ekranından varsayılan gider kategorisi seçin "
    "veya ödeme ekranında kategori seçin."
)


class DebtPlanService:
    """Manuel borç/ödeme planı yönetimi."""

    def __init__(
        self,
        debt_plan_repo: Optional[DebtPlanRepository] = None,
        bank_repo: Optional[BankRepository] = None,
        currency_repo: Optional[CurrencyRepository] = None,
        component_type_repo: Optional[ComponentTypeRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        category_repo: Optional[CategoryRepository] = None,
        credit_card_repo: Optional[CreditCardRepository] = None,
        kmh_repo: Optional[KmhRepository] = None,
        transaction_service: Optional[TransactionService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._debt_plan_repo = debt_plan_repo or DebtPlanRepository()
        self._bank_repo = bank_repo or BankRepository()
        self._currency_repo = currency_repo or CurrencyRepository()
        self._component_type_repo = component_type_repo or ComponentTypeRepository()
        self._account_repo = account_repo or AccountRepository()
        self._category_repo = category_repo or CategoryRepository()
        self._credit_card_repo = credit_card_repo or CreditCardRepository()
        self._kmh_repo = kmh_repo or KmhRepository()
        self._transaction_service = transaction_service or TransactionService()
        self._audit = audit_service or AuditService()

    def list_debt_plans(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = self._debt_plan_repo.list_debt_plans(include_inactive=include_inactive)
        return [self.format_plan_for_ui(row) for row in rows]

    def list_debt_plans_by_kind(
        self,
        plan_kind: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        self._validate_plan_kind(plan_kind)
        rows = self._debt_plan_repo.list_debt_plans_by_kind(
            plan_kind,
            include_inactive=include_inactive,
        )
        return [self.format_plan_for_ui(row) for row in rows]

    def get_debt_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        plan = self._debt_plan_repo.get_debt_plan_with_installments(plan_id)
        if plan is None:
            return None
        return self.format_plan_for_ui(plan, include_installments=True)

    def create_debt_plan(self, data: Dict[str, Any]) -> int:
        parsed = self._parse_plan_data(data)
        try:
            with get_connection() as conn:
                plan_id = self._debt_plan_repo.create_debt_plan_with_installments(
                    parsed["bank_id"],
                    parsed["plan_kind"],
                    parsed["name"],
                    parsed["principal_amount"],
                    parsed["currency_id"],
                    parsed["interest_rate"],
                    parsed["start_date"],
                    parsed["installment_count"],
                    parsed["note"],
                    parsed["source_card_id"],
                    parsed["source_kmh_id"],
                    parsed["installments"],
                    conn,
                )
                self._audit.log_create(
                    "debt_plan",
                    plan_id,
                    new_value={"name": parsed["name"], "plan_kind": parsed["plan_kind"]},
                    conn=conn,
                )
                return plan_id
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_debt_plan(self, plan_id: int, data: Dict[str, Any]) -> None:
        if self._debt_plan_repo.has_paid_installments(plan_id):
            raise ValidationError(
                "Ödenmiş taksit içeren plan bu sürümde düzenlenemez. "
                "Önce ilgili taksit ödemelerini geri alın."
            )
        parsed = self._parse_plan_data(data, for_update=True)
        is_active = bool(data.get("is_active", True))
        existing = self._debt_plan_repo.get_debt_plan(plan_id)
        try:
            with get_connection() as conn:
                self._debt_plan_repo.update_debt_plan_with_installments(
                    plan_id,
                    parsed["bank_id"],
                    parsed["plan_kind"],
                    parsed["name"],
                    parsed["principal_amount"],
                    parsed["currency_id"],
                    parsed["interest_rate"],
                    parsed["start_date"],
                    parsed["installment_count"],
                    is_active,
                    parsed["note"],
                    parsed["source_card_id"],
                    parsed["source_kmh_id"],
                    parsed["installments"],
                    conn,
                )
                if existing:
                    self._audit.log_update(
                        "debt_plan",
                        plan_id,
                        old_value={"name": existing.get("name"), "plan_kind": existing.get("plan_kind")},
                        new_value={"name": parsed["name"], "plan_kind": parsed["plan_kind"]},
                        conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_debt_plan(self, plan_id: int) -> None:
        existing = self._debt_plan_repo.get_debt_plan(plan_id)
        try:
            with get_connection() as conn:
                self._debt_plan_repo.soft_delete_debt_plan(plan_id, conn)
                if existing:
                    self._audit.log_delete(
                        "debt_plan",
                        plan_id,
                        old_value={"name": existing.get("name"), "plan_kind": existing.get("plan_kind")},
                        conn=conn,
                    )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    def get_plan_totals(self, plan_id: int) -> Dict[str, Any]:
        try:
            totals = self._debt_plan_repo.get_plan_totals(plan_id)
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        plan = self._debt_plan_repo.get_debt_plan(plan_id)
        if plan is None:
            raise ValidationError("Borç planı bulunamadı.")
        scale = int(plan["scale"])
        code = plan["currency_code"]
        symbol = plan.get("currency_symbol") or ""
        for key in (
            "principal_amount",
            "installment_total_sum",
            "unpaid_total",
            "paid_total",
            "principal_component_total",
            "expense_component_total",
        ):
            if key in totals and totals[key] is not None:
                totals[f"{key}_display"] = self._format_amount(int(totals[key]), scale, code, symbol)
        return totals

    def get_upcoming_installments(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self._debt_plan_repo.get_upcoming_installments(limit)
        return [self._format_installment_summary(row) for row in rows]

    def get_overdue_installments(self, as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
        target_date = as_of_date or date.today().isoformat()
        rows = self._debt_plan_repo.get_overdue_installments(target_date)
        return [self._format_installment_summary(row) for row in rows]

    def get_unpaid_totals_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._debt_plan_repo.get_unpaid_totals_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "unpaid_total_display": self._format_amount(
                        int(row["unpaid_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def format_plan_for_ui(
        self,
        plan: Dict[str, Any],
        include_installments: bool = False,
    ) -> Dict[str, Any]:
        scale = int(plan["scale"])
        code = plan["currency_code"]
        symbol = plan.get("currency_symbol") or ""
        formatted = {
            **plan,
            "principal_amount_display": self._format_amount(
                int(plan["principal_amount"]), scale, code, symbol
            ),
            "unpaid_total_display": self._format_amount(
                int(plan.get("unpaid_total") or 0), scale, code, symbol
            ),
            "paid_total_display": self._format_amount(
                int(plan.get("paid_total") or 0), scale, code, symbol
            ),
        }
        if include_installments and "installments" in plan:
            formatted["installments"] = [
                self._format_installment_detail(inst, scale, code, symbol)
                for inst in plan["installments"]
            ]
            formatted["totals"] = self.get_plan_totals(int(plan["id"]))
        return formatted

    def get_installment_for_payment(self, installment_id: int) -> Optional[Dict[str, Any]]:
        installment = self._debt_plan_repo.get_installment_with_components(installment_id)
        if installment is None:
            return None
        scale = int(installment["scale"])
        code = installment["currency_code"]
        symbol = installment.get("currency_symbol") or ""
        formatted = {
            **installment,
            "total_amount_display": self._format_amount(
                int(installment["total_amount"]), scale, code, symbol
            ),
            "components": [
                {
                    **comp,
                    "amount_display": self._format_amount(
                        int(comp["amount"]), scale, code, symbol
                    ),
                }
                for comp in installment.get("components", [])
            ],
        }
        return formatted

    def pay_installment(
        self,
        installment_id: int,
        account_id: int,
        paid_date: str,
        category_overrides: Optional[Dict[int, int]] = None,
    ) -> int:
        if installment_id is None:
            raise ValidationError("Taksit seçilmeden ödeme yapılamaz.")
        if account_id is None:
            raise ValidationError("Ödeme hesabı seçilmeden işlem yapılamaz.")
        if not is_non_empty_text(paid_date):
            raise ValidationError("Ödeme tarihi zorunludur.")

        installment = self._debt_plan_repo.get_installment_with_components(int(installment_id))
        if installment is None:
            raise ValidationError("Taksit bulunamadı.")

        status = str(installment["status"])
        if status == InstallmentStatus.PAID:
            raise ValidationError("Bu taksit zaten ödenmiş.")
        if status == InstallmentStatus.PARTIAL:
            raise ValidationError("Kısmi ödeme bu sürümde desteklenmiyor.")

        account = self._account_repo.get_account_with_currency(int(account_id))
        if account is None or not account.get("is_active"):
            raise ValidationError("Seçilen hesap bulunamadı veya aktif değil.")
        if int(account["currency_id"]) != int(installment["currency_id"]):
            raise ValidationError("Ödeme hesabının para birimi borç planı ile aynı olmalı.")

        total_amount = int(installment["total_amount"])
        components = installment.get("components") or []
        if not components:
            raise ValidationError("Taksit bileşenleri bulunamadı.")

        component_sum = sum(int(comp["amount"]) for comp in components)
        if component_sum != total_amount:
            raise ValidationError("Taksit bileşen toplamı taksit tutarı ile uyuşmuyor.")

        overrides = category_overrides or {}
        lines = self._build_installment_payment_lines(components, overrides)
        description = (
            f"Taksit ödemesi: {installment['plan_name']} / {installment['seq']}. taksit"
        )

        try:
            with get_connection() as conn:
                transaction_id = self._transaction_service.create_system_transaction(
                    int(account_id),
                    paid_date.strip(),
                    "out",
                    total_amount,
                    description,
                    True,
                    SOURCE_INSTALLMENT,
                    int(installment_id),
                    lines,
                    conn,
                )
                if account["tracking_mode"] == TrackingMode.LEDGER:
                    self._account_repo.adjust_balance(int(account_id), -total_amount, conn)
                self._debt_plan_repo.mark_installment_paid(
                    int(installment_id),
                    transaction_id,
                    paid_date.strip(),
                    conn,
                )
                self._audit.log_update(
                    "installment",
                    int(installment_id),
                    old_value={"status": status},
                    new_value={
                        "status": InstallmentStatus.PAID,
                        "transaction_id": transaction_id,
                        "paid_date": paid_date.strip(),
                    },
                    conn=conn,
                )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "installment_paid",
            {
                "installment_id": int(installment_id),
                "transaction_id": transaction_id,
                "account_id": int(account_id),
                "debt_plan_id": int(installment["debt_plan_id"]),
            },
        )
        event_bus.publish("transaction_created", {"transaction_id": transaction_id, "account_id": account_id})
        event_bus.publish("account_balance_changed", {"account_id": account_id})
        return transaction_id

    def unpay_installment(self, installment_id: int) -> None:
        installment = self._debt_plan_repo.get_installment_with_components(int(installment_id))
        if installment is None:
            raise ValidationError("Taksit bulunamadı.")
        if str(installment["status"]) != InstallmentStatus.PAID:
            raise ValidationError("Bu taksit ödenmiş durumda değil.")

        paid_transaction_id = installment.get("paid_transaction_id")
        if paid_transaction_id is None:
            raise ValidationError("Taksit için ödeme işlemi bulunamadı.")

        txn = self._transaction_service.get_transaction(int(paid_transaction_id))
        if txn is None:
            raise ValidationError("Taksit ödeme işlemi bulunamadı.")
        if txn.get("source_type") != SOURCE_INSTALLMENT:
            raise ValidationError("Taksit ödeme işlemi geçersiz kaynak tipine sahip.")
        if int(txn.get("source_id") or 0) != int(installment_id):
            raise ValidationError("Taksit ödeme işlemi bu taksitle eşleşmiyor.")

        account_id = int(txn["account_id"])
        try:
            with get_connection() as conn:
                self._transaction_service.reverse_transaction_balance(txn, conn)
                self._transaction_service.soft_delete_transaction_in_tx(
                    int(paid_transaction_id),
                    conn,
                )
                self._debt_plan_repo.mark_installment_unpaid(int(installment_id), conn)
                self._audit.log_update(
                    "installment",
                    int(installment_id),
                    old_value={"status": InstallmentStatus.PAID, "transaction_id": paid_transaction_id},
                    new_value={"status": InstallmentStatus.PLANNED},
                    conn=conn,
                )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        event_bus.publish(
            "installment_unpaid",
            {
                "installment_id": int(installment_id),
                "transaction_id": int(paid_transaction_id),
                "account_id": account_id,
                "debt_plan_id": int(installment["debt_plan_id"]),
            },
        )
        event_bus.publish(
            "transaction_deleted",
            {"transaction_id": int(paid_transaction_id), "account_id": account_id},
        )
        event_bus.publish("account_balance_changed", {"account_id": account_id})

    def _build_installment_payment_lines(
        self,
        components: List[Dict[str, Any]],
        category_overrides: Dict[int, int],
    ) -> List[Dict[str, Any]]:
        lines: List[Dict[str, Any]] = []
        for comp in components:
            nature = str(comp["component_nature"])
            amount = int(comp["amount"])
            component_type_id = int(comp["component_type_id"])

            if nature == Nature.PRINCIPAL:
                lines.append(
                    {
                        "nature": Nature.PRINCIPAL,
                        "category_id": None,
                        "asset_id": None,
                        "amount": amount,
                        "note": comp.get("component_name"),
                    }
                )
                continue

            if nature != Nature.EXPENSE:
                raise ValidationError("Bileşen tipi niteliği yalnızca anapara veya gider olabilir.")

            category_id = category_overrides.get(component_type_id)
            if category_id is None:
                default_category_id = comp.get("default_category_id")
                category_id = int(default_category_id) if default_category_id is not None else None
            if category_id is None:
                component_label = comp.get("component_name") or comp.get("component_code") or ""
                raise ValidationError(
                    f"{component_label}: {CATEGORY_MISSING_MESSAGE}"
                )

            category = self._category_repo.get_category(int(category_id))
            if category is None:
                raise ValidationError("Seçilen gider kategorisi bulunamadı.")
            if category["nature"] != Nature.EXPENSE:
                raise ValidationError("Gider satırı için kategori niteliği gider olmalıdır.")

            lines.append(
                {
                    "nature": Nature.EXPENSE,
                    "category_id": int(category_id),
                    "asset_id": None,
                    "amount": amount,
                    "note": comp.get("component_name"),
                }
            )

        return lines

    def _parse_plan_data(
        self,
        data: Dict[str, Any],
        for_update: bool = False,
    ) -> Dict[str, Any]:
        bank_id = data.get("bank_id")
        if bank_id is None:
            raise ValidationError("Banka seçilmeden plan oluşturulamaz.")
        bank = self._bank_repo.get_bank(int(bank_id))
        if bank is None or not bank.get("is_active"):
            raise ValidationError("Seçilen banka bulunamadı veya aktif değil.")

        plan_kind = self._validate_plan_kind(str(data.get("plan_kind") or ""))
        name = self._validate_name(str(data.get("name") or ""))

        currency_id = data.get("currency_id")
        if currency_id is None:
            raise ValidationError("Para birimi seçilmeden plan oluşturulamaz.")
        currency = self._currency_repo.get_currency(int(currency_id))
        if currency is None or not currency.get("is_active"):
            raise ValidationError("Seçilen para birimi bulunamadı veya aktif değil.")
        scale = int(currency["scale"])

        principal_amount = self._parse_amount_required(
            str(data.get("principal_amount_text") or ""),
            scale,
            "Ana para tutarı",
        )
        if principal_amount < 0:
            raise ValidationError("Ana para tutarı negatif olamaz.")

        interest_rate = self._parse_interest_rate(data.get("interest_rate"))
        start_date = self._normalize_optional_text(data.get("start_date"))
        note = self._normalize_optional_text(data.get("note"))

        raw_installments = data.get("installments") or []
        if not raw_installments and plan_kind == PlanKind.CASH_ADVANCE_INSTALLMENT:
            # Taksitli nakit avans: taksitler elle girilmediyse ana para,
            # taksit sayısı ve aylık taksit tutarından otomatik üret.
            raw_installments = self._generate_ca_installments(data, principal_amount, scale)
        if not raw_installments:
            raise ValidationError("En az bir taksit zorunludur.")

        installments = self._parse_installments(raw_installments, scale)
        installment_count = int(data.get("installment_count") or len(installments))
        if installment_count != len(installments):
            raise ValidationError(
                "Taksit sayısı, girilen taksit listesi uzunluğu ile uyuşmuyor."
            )

        source_card_id, source_kmh_id = self._validate_plan_sources(
            plan_kind,
            int(bank_id),
            int(currency_id),
            data.get("source_card_id"),
            data.get("source_kmh_id"),
        )

        return {
            "bank_id": int(bank_id),
            "plan_kind": plan_kind,
            "name": name,
            "principal_amount": principal_amount,
            "currency_id": int(currency_id),
            "interest_rate": interest_rate,
            "start_date": start_date,
            "installment_count": installment_count,
            "note": note,
            "source_card_id": source_card_id,
            "source_kmh_id": source_kmh_id,
            "installments": installments,
        }

    def _validate_plan_sources(
        self,
        plan_kind: str,
        bank_id: int,
        currency_id: int,
        source_card_id: Any,
        source_kmh_id: Any,
    ) -> tuple[Optional[int], Optional[int]]:
        card_id = None
        kmh_id = None

        if source_card_id not in (None, ""):
            card_id = int(source_card_id)
        if source_kmh_id not in (None, ""):
            kmh_id = int(source_kmh_id)

        if card_id is not None and kmh_id is not None:
            raise ValidationError(
                "Bir borç planında hem kaynak kredi kartı hem kaynak KMH seçilemez."
            )

        if card_id is not None:
            if plan_kind not in CARD_SOURCE_PLAN_KINDS:
                raise ValidationError(
                    "Kaynak kredi kartı yalnızca taksitli nakit avans veya "
                    "taksitli alışveriş planları için seçilebilir."
                )
            card = self._credit_card_repo.get_credit_card(card_id)
            if card is None or not card.get("is_active"):
                raise ValidationError("Seçilen kaynak kredi kartı bulunamadı veya aktif değil.")
            if int(card["bank_id"]) != bank_id:
                raise ValidationError("Kaynak kartın bankası plan bankası ile aynı olmalı.")
            if int(card["currency_id"]) != currency_id:
                raise ValidationError(
                    "Kaynak kartın para birimi plan para birimi ile aynı olmalı."
                )

        if kmh_id is not None:
            if plan_kind != PlanKind.KMH_INSTALLMENT:
                raise ValidationError(
                    "Kaynak KMH yalnızca taksitli KMH planları için seçilebilir."
                )
            kmh = self._kmh_repo.get_kmh_account_with_details(kmh_id)
            if kmh is None or not kmh.get("is_active"):
                raise ValidationError("Seçilen kaynak KMH bulunamadı veya aktif değil.")
            if int(kmh["bank_id"]) != bank_id:
                raise ValidationError("Kaynak KMH bankası plan bankası ile aynı olmalı.")
            if int(kmh["currency_id"]) != currency_id:
                raise ValidationError(
                    "Kaynak KMH para birimi plan para birimi ile aynı olmalı."
                )

        if plan_kind == PlanKind.LOAN and (card_id is not None or kmh_id is not None):
            raise ValidationError("Kredi planında kaynak kart veya KMH seçilemez.")

        return card_id, kmh_id

    @staticmethod
    def _add_months(date_str: str, months: int) -> str:
        """'yyyy-MM-dd' tarihine ay ekler; gün ay sonunu aşarsa ay sonuna sabitler."""
        import calendar

        year, month, day = (int(part) for part in date_str.split("-"))
        total = (month - 1) + months
        new_year = year + total // 12
        new_month = total % 12 + 1
        last_day = calendar.monthrange(new_year, new_month)[1]
        new_day = min(day, last_day)
        return f"{new_year:04d}-{new_month:02d}-{new_day:02d}"

    def _generate_ca_installments(
        self,
        data: Dict[str, Any],
        principal_amount: int,
        scale: int,
    ) -> List[Dict[str, Any]]:
        """Taksitli nakit avans taksitlerini eşit (yuvarlama farkı son taksitte)
        anapara + faiz bileşenleriyle üretir."""
        count = int(data.get("ca_installment_count") or 0)
        if count <= 0:
            raise ValidationError("Taksitli nakit avans için taksit sayısı girilmelidir.")
        if principal_amount <= 0:
            raise ValidationError("Taksitli nakit avansta ana para sıfırdan büyük olmalıdır.")

        monthly = self._parse_amount_required(
            str(data.get("ca_monthly_payment_text") or ""),
            scale,
            "Aylık taksit tutarı",
        )
        if monthly <= 0:
            raise ValidationError("Aylık taksit tutarı sıfırdan büyük olmalıdır.")

        first_due = str(
            data.get("ca_first_due_date") or data.get("start_date") or ""
        ).strip()
        if not first_due:
            raise ValidationError("Taksitli nakit avans için ilk taksit vadesi girilmelidir.")

        total_repay = monthly * count
        total_interest = total_repay - principal_amount
        if total_interest < 0:
            raise ValidationError(
                "Aylık taksit tutarı × taksit sayısı, ana paradan küçük olamaz."
            )

        type_ids = {
            str(ct["code"]): int(ct["id"])
            for ct in self._component_type_repo.list_component_types()
        }
        principal_type_id = type_ids.get("principal")
        interest_type_id = type_ids.get("interest")
        if principal_type_id is None:
            raise ValidationError("'Anapara' bileşen tipi tanımlı değil.")
        if total_interest > 0 and interest_type_id is None:
            raise ValidationError("'Faiz' bileşen tipi tanımlı değil.")

        principal_each = principal_amount // count
        interest_each = total_interest // count

        raw: List[Dict[str, Any]] = []
        principal_acc = 0
        for k in range(1, count + 1):
            if k < count:
                principal_k = principal_each
                interest_k = interest_each
            else:
                # Son taksit yuvarlama farkını üstlenir.
                principal_k = principal_amount - principal_each * (count - 1)
                interest_k = total_interest - interest_each * (count - 1)
            principal_acc += principal_k
            remaining_after = principal_amount - principal_acc

            components = [
                {
                    "component_type_id": principal_type_id,
                    "amount_text": format_amount(principal_k, scale),
                }
            ]
            if interest_k > 0:
                components.append(
                    {
                        "component_type_id": interest_type_id,
                        "amount_text": format_amount(interest_k, scale),
                    }
                )

            raw.append(
                {
                    "seq": k,
                    "due_date": self._add_months(first_due, k - 1),
                    "total_amount_text": format_amount(principal_k + interest_k, scale),
                    "remaining_principal_after_text": format_amount(remaining_after, scale),
                    "components": components,
                }
            )
        return raw

    def _parse_installments(
        self,
        raw_installments: List[Dict[str, Any]],
        scale: int,
    ) -> List[Dict[str, Any]]:
        seen_seq: Set[int] = set()
        parsed: List[Dict[str, Any]] = []
        component_types = {
            int(ct["id"]): ct
            for ct in self._component_type_repo.list_component_types()
        }

        for inst in raw_installments:
            seq = inst.get("seq")
            if seq is None or int(seq) <= 0:
                raise ValidationError("Her taksitte sıra numarası pozitif olmalıdır.")
            seq_int = int(seq)
            if seq_int in seen_seq:
                raise ValidationError(f"Taksit sıra numarası tekrar ediyor: {seq_int}")
            seen_seq.add(seq_int)

            due_date = str(inst.get("due_date") or "").strip()
            if not due_date:
                raise ValidationError("Her taksitte vade tarihi zorunludur.")

            total_amount = self._parse_amount_required(
                str(inst.get("total_amount_text") or inst.get("total_amount") or ""),
                scale,
                "Taksit toplam tutarı",
            )
            if total_amount <= 0:
                raise ValidationError("Taksit toplam tutarı sıfırdan büyük olmalıdır.")

            remaining_text = inst.get("remaining_principal_after_text")
            remaining_principal_after = None
            if remaining_text is not None and str(remaining_text).strip():
                remaining_principal_after = self._parse_amount_required(
                    str(remaining_text),
                    scale,
                    "Kalan anapara",
                )

            components_raw = inst.get("components") or []
            if not components_raw:
                raise ValidationError(f"{seq_int}. taksitte en az bir bileşen zorunludur.")

            components: List[Dict[str, Any]] = []
            component_sum = 0
            for comp in components_raw:
                comp_type_id = comp.get("component_type_id")
                if comp_type_id is None:
                    raise ValidationError("Bileşen tipi seçilmelidir.")
                comp_type = component_types.get(int(comp_type_id))
                if comp_type is None:
                    raise ValidationError("Seçilen bileşen tipi bulunamadı.")
                if comp_type["nature"] not in VALID_COMPONENT_NATURES:
                    raise ValidationError(
                        "Bileşen tipi niteliği yalnızca anapara veya gider olabilir."
                    )
                amount_text = comp.get("amount_text") or comp.get("amount")
                amount = self._parse_amount_required(
                    str(amount_text),
                    scale,
                    "Bileşen tutarı",
                )
                if amount < 0:
                    raise ValidationError("Bileşen tutarı negatif olamaz.")
                component_sum += amount
                components.append(
                    {
                        "component_type_id": int(comp_type_id),
                        "amount": amount,
                    }
                )

            if component_sum != total_amount:
                raise ValidationError(
                    f"{seq_int}. taksitte bileşen toplamı taksit tutarına eşit olmalıdır."
                )

            parsed.append(
                {
                    "seq": seq_int,
                    "due_date": due_date,
                    "total_amount": total_amount,
                    "remaining_principal_after": remaining_principal_after,
                    "note": self._normalize_optional_text(inst.get("note")),
                    "components": components,
                }
            )

        return sorted(parsed, key=lambda item: item["seq"])

    def _format_installment_detail(
        self,
        inst: Dict[str, Any],
        scale: int,
        code: str,
        symbol: str,
    ) -> Dict[str, Any]:
        formatted = {
            **inst,
            "total_amount_display": self._format_amount(
                int(inst["total_amount"]), scale, code, symbol
            ),
        }
        if inst.get("remaining_principal_after") is not None:
            formatted["remaining_principal_after_display"] = self._format_amount(
                int(inst["remaining_principal_after"]), scale, code, symbol
            )
        formatted["components"] = [
            {
                **comp,
                "amount_display": self._format_amount(
                    int(comp["amount"]), scale, code, symbol
                ),
            }
            for comp in inst.get("components", [])
        ]
        return formatted

    def _format_installment_summary(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **row,
            "total_amount_display": self._format_amount(
                int(row["total_amount"]),
                int(row["scale"]),
                row["currency_code"],
                row.get("currency_symbol") or "",
            ),
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

    def _validate_plan_kind(self, plan_kind: str) -> str:
        normalized = (plan_kind or "").strip().lower()
        if normalized not in VALID_PLAN_KINDS:
            raise ValidationError("Geçersiz plan türü.")
        return normalized

    def _validate_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Plan adı boş olamaz.")
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
