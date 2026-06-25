"""§11 negatif bakiye uyarısı: engellemez, yalnızca uyarır."""

import unittest

from app.core.constants import Nature, TrackingMode
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.transaction_service import TransactionService
from tests._base import DBTestCase


class NegativeBalanceWarningTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.accounts = AccountService()
        self.txns = TransactionService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")

    def _account(self, opening="0", mode=TrackingMode.LEDGER):
        return self.accounts.create_account(
            self.bank_id, "Vadesiz", self.try_id, opening, tracking_mode=mode
        )

    def test_warns_when_outflow_exceeds_balance(self):
        acc = self._account(opening="100,00")
        warning = self.txns.negative_balance_warning(acc, "out", "150,00")
        self.assertIsNotNone(warning)

    def test_no_warning_when_within_balance(self):
        acc = self._account(opening="100,00")
        self.assertIsNone(self.txns.negative_balance_warning(acc, "out", "100,00"))

    def test_no_warning_for_income(self):
        acc = self._account(opening="0")
        self.assertIsNone(self.txns.negative_balance_warning(acc, "in", "999,00"))

    def test_no_warning_for_snapshot_account(self):
        acc = self._account(opening="0", mode=TrackingMode.SNAPSHOT)
        self.assertIsNone(self.txns.negative_balance_warning(acc, "out", "999,00"))

    def test_warning_is_only_advisory_not_blocking(self):
        # Uyarı dönse bile işlem yine de oluşturulabilmeli (engellenmemeli)
        acc = self._account(opening="100,00")
        self.assertIsNotNone(self.txns.negative_balance_warning(acc, "out", "150,00"))
        txn_id = self.txns.create_transaction(
            acc, "2026-01-01", "out", "150,00", None, True,
            [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
              "amount_text": "150,00"}],
        )
        self.assertIsNotNone(txn_id)
        self.assertEqual(int(self.accounts.get_account(acc)["current_balance"]), -5000)

    def test_edit_excludes_own_old_effect(self):
        # Hesapta 100,00 var; 80,00 çıkış işlemi -> bakiye 20,00
        acc = self._account(opening="100,00")
        txn_id = self.txns.create_transaction(
            acc, "2026-01-01", "out", "80,00", None, True,
            [{"nature": Nature.EXPENSE, "category_id": self.category_id("Yakıt"),
              "amount_text": "80,00"}],
        )
        # Aynı işlemi 90,00'a düzenlemek: eski 80 geri alınır, 90 uygulanır ->
        # 100 - 90 = 10,00 (>=0) yani UYARI OLMAMALI. Eski etki dışlanmazsa
        # 20 - 90 = -70 ile yanlış uyarı çıkardı.
        warning = self.txns.negative_balance_warning(
            acc, "out", "90,00", exclude_transaction_id=txn_id
        )
        self.assertIsNone(warning)

    def test_for_amount_variant(self):
        acc = self._account(opening="100,00")
        # 150,00 = 15000 en-küçük-birim
        self.assertIsNotNone(
            self.txns.negative_balance_warning_for_amount(acc, "out", 15000)
        )
        self.assertIsNone(
            self.txns.negative_balance_warning_for_amount(acc, "out", 5000)
        )


if __name__ == "__main__":
    unittest.main()
