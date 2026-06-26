"""Aşama 2: kredi kartı tekil hareketleri (card_entries)."""

import unittest

from app.core.constants import CardEntryType
from app.core.exceptions import ValidationError
from app.services.bank_service import BankService
from app.services.card_entry_service import CardEntryService
from app.services.credit_card_service import CreditCardService
from tests._base import DBTestCase


class CardEntryTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.entries = CardEntryService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.card_id = CreditCardService().create_credit_card({
            "bank_id": self.bank_id, "name": "Kart", "currency_id": self.try_id,
            "card_limit_text": "100.000,00", "cash_advance_limit_text": "25.000,00",
            "counts_as_liquidity": False,
        })

    def _add(self, entry_type, amount, category_id=None):
        return self.entries.create_entry({
            "credit_card_id": self.card_id,
            "txn_date": "2026-06-01",
            "entry_type": entry_type,
            "amount_text": amount,
            "category_id": category_id,
        })

    def test_purchase_with_category_counts_as_debt(self):
        self._add(CardEntryType.PURCHASE, "1.000,00", self.category_id("Yakıt"))
        totals = self.entries.get_entry_totals(self.card_id)
        self.assertEqual(totals["charges"], 100000)
        self.assertEqual(totals["debt"], 100000)
        self.assertEqual(totals["cash_advance_charged"], 0)

    def test_cash_advance_counts_separately(self):
        self._add(CardEntryType.CASH_ADVANCE, "5.000,00")
        totals = self.entries.get_entry_totals(self.card_id)
        self.assertEqual(totals["cash_advance_charged"], 500000)
        self.assertEqual(totals["debt"], 500000)

    def test_payment_reduces_debt(self):
        self._add(CardEntryType.PURCHASE, "1.000,00", self.category_id("Yakıt"))
        self._add(CardEntryType.PAYMENT, "400,00")
        totals = self.entries.get_entry_totals(self.card_id)
        self.assertEqual(totals["debt"], 60000)  # 1000 - 400

    def test_payment_cannot_have_category(self):
        with self.assertRaises(ValidationError):
            self._add(CardEntryType.PAYMENT, "400,00", self.category_id("Yakıt"))

    def test_purchase_category_must_be_expense(self):
        with self.assertRaises(ValidationError):
            self._add(CardEntryType.PURCHASE, "100,00", self.category_id("Maaş"))

    def test_delete_removes_from_totals(self):
        eid = self._add(CardEntryType.PURCHASE, "1.000,00")
        self.entries.delete_entry(eid)
        self.assertEqual(self.entries.get_entry_totals(self.card_id)["debt"], 0)

    def test_zero_amount_rejected(self):
        with self.assertRaises(ValidationError):
            self._add(CardEntryType.PURCHASE, "0,00")


if __name__ == "__main__":
    unittest.main()
