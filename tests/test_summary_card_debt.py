"""Aşama 5c: Banka Özeti kredi kartı borcu = türetilen ekstre dönem borcu."""

import unittest

from app.core.constants import CardEntryType
from app.services.bank_service import BankService
from app.services.card_entry_service import CardEntryService
from app.services.credit_card_service import CreditCardService
from app.services.summary_service import SummaryService
from tests._base import DBTestCase


class SummaryCardDebtTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.card_id = CreditCardService().create_credit_card({
            "bank_id": self.bank_id, "name": "Kart", "currency_id": self.try_id,
            "card_limit_text": "100.000,00", "cash_advance_limit_text": "25.000,00",
            "statement_day": 10, "due_day": 20, "counts_as_liquidity": False,
        })

    def test_summary_reflects_derived_debt(self):
        ce = CardEntryService()
        ce.create_entry({"credit_card_id": self.card_id, "txn_date": "2026-06-05",
                         "entry_type": CardEntryType.PURCHASE, "amount_text": "1.000,00"})
        ce.create_entry({"credit_card_id": self.card_id, "txn_date": "2026-06-06",
                         "entry_type": CardEntryType.PAYMENT, "amount_text": "300,00"})
        rows = {r["currency_id"]: r for r in
                SummaryService().get_credit_card_debts_by_currency()}
        self.assertEqual(int(rows[self.try_id]["statement_debt_total"]), 70000)  # 1000-300

    def test_no_activity_no_card_debt(self):
        self.assertEqual(SummaryService().get_credit_card_debts_by_currency(), [])


if __name__ == "__main__":
    unittest.main()
