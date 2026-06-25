"""account_service — reconcile ve sıfır-bakiye koruması (§9.3, §11)."""

import unittest

from app.core.constants import Nature
from app.core.exceptions import ValidationError
from app.repositories.account_repository import AccountRepository
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.transaction_service import TransactionService
from tests._base import DBTestCase


class AccountServiceTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.accounts = AccountService()
        self.txns = TransactionService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")

    def _account(self, opening="0"):
        return self.accounts.create_account(self.bank_id, "Vadesiz", self.try_id, opening)

    def test_reconcile_matches_after_transaction(self):
        acc = self._account(opening="1.000,00")
        self.txns.create_transaction(
            acc, "2026-01-01", "in", "200,00", None, True,
            [{"nature": Nature.INCOME, "category_id": self.category_id("Maaş"),
              "amount_text": "200,00"}],
        )
        self.assertEqual(self.accounts.reconcile_balance(acc), 120000)

    def test_reconcile_detects_drift(self):
        acc = self._account(opening="1.000,00")
        # current_balance'ı bilerek boz
        with __import__("app.core.database", fromlist=["get_connection"]).get_connection() as conn:
            AccountRepository().set_current_balance(acc, 999, conn)
        results = {r["account_id"]: r for r in self.accounts.reconcile_all_accounts()}
        self.assertEqual(results[acc]["status"], "drift")
        self.accounts.fix_account_balance_from_reconcile(acc)
        results = {r["account_id"]: r for r in self.accounts.reconcile_all_accounts()}
        self.assertEqual(results[acc]["status"], "ok")

    def test_cannot_delete_account_with_balance(self):
        acc = self._account(opening="500,00")
        with self.assertRaises(ValidationError):
            self.accounts.delete_account(acc)


if __name__ == "__main__":
    unittest.main()
