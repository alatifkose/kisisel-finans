"""transaction_service — split motoru ve bakiye etkisi (§9)."""

import unittest

from app.core.constants import Nature, TrackingMode
from app.core.exceptions import ValidationError
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.transaction_service import TransactionService
from tests._base import DBTestCase


class TransactionServiceTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.banks = BankService()
        self.accounts = AccountService()
        self.txns = TransactionService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = self.banks.create_bank("Test Bank")

    def _account(self, opening="0", mode=TrackingMode.LEDGER):
        return self.accounts.create_account(
            self.bank_id, "Vadesiz", self.try_id, opening, tracking_mode=mode
        )

    def _balance(self, account_id):
        return int(self.accounts.get_account(account_id)["current_balance"])

    def test_expense_decreases_ledger_balance(self):
        acc = self._account(opening="1.000,00")
        self.txns.create_transaction(
            acc, "2026-01-01", "out", "100,00", "Yakıt", True,
            [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
              "amount_text": "100,00"}],
        )
        self.assertEqual(self._balance(acc), 90000)  # 900,00

    def test_income_increases_balance(self):
        acc = self._account(opening="0")
        self.txns.create_transaction(
            acc, "2026-01-01", "in", "5.000,00", "Maaş", True,
            [{"nature": Nature.INCOME, "category_id": self.category_id("Maaş"),
              "amount_text": "5.000,00"}],
        )
        self.assertEqual(self._balance(acc), 500000)

    def test_split_sum_must_equal_total(self):
        acc = self._account(opening="1.000,00")
        with self.assertRaises(ValidationError):
            self.txns.create_transaction(
                acc, "2026-01-01", "out", "100,00", None, True,
                [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
                  "amount_text": "50,00"}],  # toplam 100 ama satır 50
            )

    def test_category_nature_must_match_line_nature(self):
        acc = self._account(opening="1.000,00")
        with self.assertRaises(ValidationError):
            self.txns.create_transaction(
                acc, "2026-01-01", "out", "100,00", None, True,
                # gider satırına gelir kategorisi (Maaş)
                [{"nature": Nature.EXPENSE, "category_id": self.category_id("Maaş"),
                  "amount_text": "100,00"}],
            )

    def test_snapshot_account_balance_unchanged(self):
        acc = self._account(opening="1.000,00", mode=TrackingMode.SNAPSHOT)
        self.txns.create_transaction(
            acc, "2026-01-01", "out", "100,00", None, True,
            [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
              "amount_text": "100,00"}],
        )
        self.assertEqual(self._balance(acc), 100000)  # değişmedi

    def test_delete_reverses_balance(self):
        acc = self._account(opening="1.000,00")
        txn_id = self.txns.create_transaction(
            acc, "2026-01-01", "out", "100,00", None, True,
            [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
              "amount_text": "100,00"}],
        )
        self.assertEqual(self._balance(acc), 90000)
        self.txns.delete_transaction(txn_id)
        self.assertEqual(self._balance(acc), 100000)  # geri alındı


if __name__ == "__main__":
    unittest.main()
