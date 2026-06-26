"""Aşama 4: türetilen kredi kartı ekstresi."""

import unittest

from app.core.constants import CardEntryType, PlanKind
from app.services.bank_service import BankService
from app.services.card_entry_service import CardEntryService
from app.services.card_statement_service import CardStatementService
from app.services.credit_card_service import CreditCardService
from app.services.debt_plan_service import DebtPlanService
from tests._base import DBTestCase


class CardStatementTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.entries = CardEntryService()
        self.plans = DebtPlanService()
        self.stmt = CardStatementService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.card_id = CreditCardService().create_credit_card({
            "bank_id": self.bank_id, "name": "Kart", "currency_id": self.try_id,
            "card_limit_text": "100.000,00", "cash_advance_limit_text": "25.000,00",
            "statement_day": 10, "due_day": 20, "counts_as_liquidity": False,
        })

    def _entry(self, etype, amount, day, category_id=None):
        return self.entries.create_entry({
            "credit_card_id": self.card_id, "txn_date": day,
            "entry_type": etype, "amount_text": amount, "category_id": category_id,
        })

    def test_single_purchase_one_period(self):
        self._entry(CardEntryType.PURCHASE, "1.000,00", "2026-06-05",
                    self.category_id("Yakıt"))
        periods = self.stmt.get_statements(self.card_id)
        self.assertEqual(len(periods), 1)
        p = periods[0]
        self.assertEqual(p["cut_date"], "2026-06-10")
        self.assertEqual(p["due_date"], "2026-06-20")
        self.assertEqual(p["opening_balance"], 0)
        self.assertEqual(p["period_debt"], 100000)
        self.assertEqual(len(p["lines"]), 1)

    def test_purchase_and_payment_same_period(self):
        self._entry(CardEntryType.PURCHASE, "500,00", "2026-06-05",
                    self.category_id("Yakıt"))
        self._entry(CardEntryType.PAYMENT, "200,00", "2026-06-08")
        p = self.stmt.get_statements(self.card_id)[0]
        self.assertEqual(p["charges"], 50000)
        self.assertEqual(p["payments"], 20000)
        self.assertEqual(p["period_debt"], 30000)

    def test_carry_over_between_periods(self):
        self._entry(CardEntryType.PURCHASE, "1.000,00", "2026-06-05")
        self._entry(CardEntryType.PURCHASE, "500,00", "2026-06-15")  # sonraki dönem
        periods = self.stmt.get_statements(self.card_id)
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]["period_debt"], 100000)
        self.assertEqual(periods[1]["opening_balance"], 100000)
        self.assertEqual(periods[1]["period_debt"], 150000)

    def test_installments_spread_across_periods(self):
        # 3 taksitli nakit avans, vadeler 3 ayrı ay
        self.plans.create_debt_plan({
            "bank_id": self.bank_id, "plan_kind": PlanKind.CASH_ADVANCE_INSTALLMENT,
            "name": "TNA", "currency_id": self.try_id,
            "principal_amount_text": "3.000,00", "installment_count": 3,
            "source_card_id": self.card_id,
            "installments": [
                {"seq": 1, "due_date": "2026-07-01", "total_amount_text": "1.000,00",
                 "components": [{"component_type_id": self.component_type_id("principal"),
                                "amount_text": "1.000,00"}]},
                {"seq": 2, "due_date": "2026-08-01", "total_amount_text": "1.000,00",
                 "components": [{"component_type_id": self.component_type_id("principal"),
                                "amount_text": "1.000,00"}]},
                {"seq": 3, "due_date": "2026-09-01", "total_amount_text": "1.000,00",
                 "components": [{"component_type_id": self.component_type_id("principal"),
                                "amount_text": "1.000,00"}]},
            ],
        })
        periods = self.stmt.get_statements(self.card_id)
        self.assertEqual(len(periods), 3)
        # Ödeme yoksa borç birikir
        self.assertEqual([p["period_debt"] for p in periods], [100000, 200000, 300000])
        for p in periods:
            self.assertEqual(len(p["lines"]), 1)
            self.assertEqual(p["lines"][0]["kind"], "installment")

    def test_no_activity_returns_empty(self):
        self.assertEqual(self.stmt.get_statements(self.card_id), [])


if __name__ == "__main__":
    unittest.main()
