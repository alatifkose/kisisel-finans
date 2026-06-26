"""Taksitli nakit avans: basit giriş (ana para + taksit sayısı + aylık taksit)
otomatik anapara/faiz dağılımı üretir; faiz dahil tüm borç likiditeyi düşürür."""

import unittest

from app.core.constants import PlanKind
from app.core.exceptions import ValidationError
from app.repositories.credit_card_repository import CreditCardRepository
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.credit_card_service import CreditCardService
from app.services.debt_plan_service import DebtPlanService
from tests._base import DBTestCase


class CaInstallmentAutogenTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.plans = DebtPlanService()
        self.accounts = AccountService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.account_id = self.accounts.create_account(
            self.bank_id, "Vadesiz", self.try_id, "100.000,00"
        )
        self.card_id = CreditCardService().create_credit_card({
            "bank_id": self.bank_id, "name": "Kart", "currency_id": self.try_id,
            "card_limit_text": "100.000,00", "cash_advance_limit_text": "25.000,00",
            "counts_as_liquidity": False,
        })

    def _create_plan(self, principal="25.000,00", count=3, monthly="8.721,81",
                     first_due="2026-07-20"):
        return self.plans.create_debt_plan({
            "bank_id": self.bank_id,
            "plan_kind": PlanKind.CASH_ADVANCE_INSTALLMENT,
            "name": "Nakit Avans 3 Taksit",
            "currency_id": self.try_id,
            "source_card_id": self.card_id,
            "principal_amount_text": principal,
            "ca_installment_count": count,
            "ca_monthly_payment_text": monthly,
            "ca_first_due_date": first_due,
            "installments": [],
        })

    def _available(self):
        rows = {r["currency_id"]: r for r in
                CreditCardRepository().get_cash_advance_available_by_currency()}
        return int(rows[self.try_id]["available_total"]) if self.try_id in rows else 0

    def test_generates_equal_installments_with_remainder_on_last(self):
        plan_id = self._create_plan()
        insts = sorted(self.plans.get_debt_plan(plan_id)["installments"],
                       key=lambda x: x["seq"])
        self.assertEqual(len(insts), 3)
        # Toplam geri ödeme = 8.721,81 × 3 = 26.165,43
        self.assertEqual(sum(int(i["total_amount"]) for i in insts), 2616543)
        # Vade tarihleri aylık ilerler
        self.assertEqual([i["due_date"] for i in insts],
                         ["2026-07-20", "2026-08-20", "2026-09-20"])

    def test_principal_components_sum_to_principal(self):
        plan_id = self._create_plan()
        insts = self.plans.get_debt_plan(plan_id)["installments"]
        principal_total = 0
        for inst in insts:
            full = self.plans.get_installment_for_payment(int(inst["id"]))
            for comp in full["components"]:
                if str(comp["component_nature"]) == "principal":
                    principal_total += int(comp["amount"])
        self.assertEqual(principal_total, 2500000)  # 25.000,00

    def test_full_debt_including_interest_reduces_liquidity(self):
        # Toplam borç 26.165,43 > 25.000 limit → kullanılabilir nakit avans 0
        self._create_plan()
        self.assertEqual(self._available(), 0)

    def test_paying_installments_restores_liquidity(self):
        plan_id = self._create_plan()
        insts = sorted(self.plans.get_debt_plan(plan_id)["installments"],
                       key=lambda x: x["seq"])
        self.plans.pay_installment(int(insts[0]["id"]), self.account_id, "2026-07-20")
        self.plans.pay_installment(int(insts[1]["id"]), self.account_id, "2026-08-20")
        # Kalan tek taksit borcu = 3. taksit toplamı
        remaining = int(insts[2]["total_amount"])
        self.assertEqual(self._available(), 2500000 - remaining)

    def test_monthly_times_count_less_than_principal_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_plan(principal="25.000,00", count=3, monthly="1.000,00")


if __name__ == "__main__":
    unittest.main()
