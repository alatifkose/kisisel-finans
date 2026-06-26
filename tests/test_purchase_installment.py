"""Aşama 3: taksitli alışveriş plan türü (purchase_installment)."""

import unittest

from app.core.constants import PlanKind
from app.core.exceptions import ValidationError
from app.repositories.credit_card_repository import CreditCardRepository
from app.services.bank_service import BankService
from app.services.credit_card_service import CreditCardService
from app.services.debt_plan_service import DebtPlanService
from tests._base import DBTestCase


class PurchaseInstallmentTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.plans = DebtPlanService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.card_id = CreditCardService().create_credit_card({
            "bank_id": self.bank_id, "name": "Kart", "currency_id": self.try_id,
            "card_limit_text": "100.000,00", "cash_advance_limit_text": "25.000,00",
            "counts_as_liquidity": False,
        })

    def _plan(self, kind, source_card_id=None, principal="6.000,00"):
        return self.plans.create_debt_plan({
            "bank_id": self.bank_id,
            "plan_kind": kind,
            "name": kind,
            "currency_id": self.try_id,
            "principal_amount_text": principal,
            "installment_count": 1,
            "source_card_id": source_card_id,
            "installments": [{
                "seq": 1, "due_date": "2026-07-01", "total_amount_text": principal,
                "components": [{"component_type_id": self.component_type_id("principal"),
                               "amount_text": principal}],
            }],
        })

    def test_purchase_installment_can_link_to_card(self):
        plan_id = self._plan(PlanKind.PURCHASE_INSTALLMENT, self.card_id)
        plan = self.plans.get_debt_plan(plan_id)
        self.assertEqual(plan["plan_kind"], PlanKind.PURCHASE_INSTALLMENT)
        self.assertEqual(int(plan["source_card_id"]), self.card_id)

    def test_purchase_installment_does_not_consume_cash_advance(self):
        self._plan(PlanKind.PURCHASE_INSTALLMENT, self.card_id, "10.000,00")
        rows = {r["currency_id"]: r for r in
                CreditCardRepository().get_cash_advance_available_by_currency()}
        # Taksitli alışveriş nakit avans limitini düşürmez -> tam 25.000 kalır
        self.assertEqual(int(rows[self.try_id]["available_total"]), 2500000)

    def test_cash_advance_installment_still_consumes_limit(self):
        self._plan(PlanKind.CASH_ADVANCE_INSTALLMENT, self.card_id, "10.000,00")
        rows = {r["currency_id"]: r for r in
                CreditCardRepository().get_cash_advance_available_by_currency()}
        self.assertEqual(int(rows[self.try_id]["available_total"]), 1500000)  # 25k-10k

    def test_loan_rejects_source_card(self):
        with self.assertRaises(ValidationError):
            self._plan(PlanKind.LOAN, self.card_id)


if __name__ == "__main__":
    unittest.main()
