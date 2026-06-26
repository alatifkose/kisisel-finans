"""Aşama 1: ayrı nakit avans limiti + likiditeye yansıması."""

import unittest

from app.core.constants import PlanKind
from app.core.exceptions import ValidationError
from app.repositories.credit_card_repository import CreditCardRepository
from app.services.bank_service import BankService
from app.services.credit_card_service import CreditCardService
from app.services.debt_plan_service import DebtPlanService
from app.services.summary_service import SummaryService
from tests._base import DBTestCase


class CardCashAdvanceTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.cards = CreditCardService()
        self.plans = DebtPlanService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")

    def _card(self, card_limit="100.000,00", cash="25.000,00"):
        return self.cards.create_credit_card({
            "bank_id": self.bank_id,
            "name": "Test Kart",
            "currency_id": self.try_id,
            "card_limit_text": card_limit,
            "cash_advance_limit_text": cash,
            "counts_as_liquidity": False,
        })

    def test_cash_advance_limit_cannot_exceed_card_limit(self):
        with self.assertRaises(ValidationError):
            self._card(card_limit="10.000,00", cash="25.000,00")

    def test_available_cash_advance_appears_in_liquidity(self):
        self._card()
        rows = {r["currency_id"]: r for r in
                self.cards.get_cash_advance_available_by_currency()}
        self.assertEqual(int(rows[self.try_id]["available_total"]), 2500000)  # 25.000,00

        liq = {r["currency_id"]: r for r in SummaryService().get_available_liquidity()}
        self.assertEqual(int(liq[self.try_id]["card_cash_advance_available"]["raw"]), 2500000)
        self.assertEqual(int(liq[self.try_id]["total_liquidity"]["raw"]), 2500000)

    def test_installment_cash_advance_consumes_limit(self):
        card_id = self._card()
        # 25.000 taksitli nakit avans, tek taksit, anapara bileşeni 25.000
        self.plans.create_debt_plan({
            "bank_id": self.bank_id,
            "plan_kind": PlanKind.CASH_ADVANCE_INSTALLMENT,
            "name": "Taksitli Nakit Avans",
            "currency_id": self.try_id,
            "principal_amount_text": "25.000,00",
            "installment_count": 1,
            "source_card_id": card_id,
            "installments": [{
                "seq": 1, "due_date": "2026-07-01", "total_amount_text": "25.000,00",
                "components": [{"component_type_id": self.component_type_id("principal"),
                               "amount_text": "25.000,00"}],
            }],
        })
        # Tüm nakit avans limiti tükendi -> kullanılabilir 0
        rows = {r["currency_id"]: r for r in
                CreditCardRepository().get_cash_advance_available_by_currency()}
        self.assertEqual(int(rows[self.try_id]["available_total"]), 0)


if __name__ == "__main__":
    unittest.main()
