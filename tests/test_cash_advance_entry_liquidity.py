"""Aşama 5d: taksitsiz nakit avans hareketleri nakit avans likiditesini düşürür."""

import unittest

from app.core.constants import CardEntryType
from app.repositories.credit_card_repository import CreditCardRepository
from app.services.bank_service import BankService
from app.services.card_entry_service import CardEntryService
from app.services.credit_card_service import CreditCardService
from tests._base import DBTestCase


class CashAdvanceEntryLiquidityTests(DBTestCase):
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

    def _available(self):
        rows = {r["currency_id"]: r for r in
                CreditCardRepository().get_cash_advance_available_by_currency()}
        return int(rows[self.try_id]["available_total"]) if self.try_id in rows else 0

    def _add(self, etype, amount):
        self.entries.create_entry({"credit_card_id": self.card_id, "txn_date": "2026-06-01",
                                   "entry_type": etype, "amount_text": amount})

    def test_cash_advance_entry_reduces_available(self):
        self._add(CardEntryType.CASH_ADVANCE, "5.000,00")
        self.assertEqual(self._available(), 2000000)  # 25k - 5k

    def test_payment_restores_available(self):
        self._add(CardEntryType.CASH_ADVANCE, "5.000,00")
        self._add(CardEntryType.PAYMENT, "5.000,00")
        self.assertEqual(self._available(), 2500000)

    def test_overpayment_does_not_exceed_limit(self):
        self._add(CardEntryType.CASH_ADVANCE, "5.000,00")
        self._add(CardEntryType.PAYMENT, "8.000,00")
        self.assertEqual(self._available(), 2500000)  # MAX(.,0) -> tam limit


if __name__ == "__main__":
    unittest.main()
