"""debt_plan_service — omurganın kalbi: taksit ödemesi niteliğe göre bölünür (§9.4).

Bir taksit ödendiğinde anapara payı 'principal' (borç azaltır), faiz/vergi payı
'expense' (gerçek gider) satırı olur. "Ne harcadım" sorusu buna bağlı.
"""

import unittest

from app.core.constants import InstallmentStatus, Nature, PlanKind
from app.core.exceptions import ValidationError
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.debt_plan_service import DebtPlanService
from app.services.transaction_service import TransactionService
from tests._base import DBTestCase


class DebtPlanPaymentTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.accounts = AccountService()
        self.plans = DebtPlanService()
        self.txns = TransactionService()
        self.try_id = self.currency_id("TRY")
        self.bank_id = BankService().create_bank("Test Bank")
        self.account_id = self.accounts.create_account(
            self.bank_id, "Vadesiz", self.try_id, "10.000,00"
        )

    def _create_single_installment_plan(self):
        # 1 taksit: 600,00 anapara + 400,00 faiz = 1.000,00
        data = {
            "bank_id": self.bank_id,
            "plan_kind": PlanKind.LOAN,
            "name": "İhtiyaç Kredisi",
            "currency_id": self.try_id,
            "principal_amount_text": "600,00",
            "installment_count": 1,
            "installments": [
                {
                    "seq": 1,
                    "due_date": "2026-02-01",
                    "total_amount_text": "1.000,00",
                    "components": [
                        {"component_type_id": self.component_type_id("principal"),
                         "amount_text": "600,00"},
                        {"component_type_id": self.component_type_id("interest"),
                         "amount_text": "400,00"},
                    ],
                }
            ],
        }
        plan_id = self.plans.create_debt_plan(data)
        plan = self.plans.get_debt_plan(plan_id)
        return plan_id, int(plan["installments"][0]["id"])

    def test_component_sum_mismatch_rejected(self):
        data = {
            "bank_id": self.bank_id, "plan_kind": PlanKind.LOAN, "name": "Hatalı",
            "currency_id": self.try_id, "principal_amount_text": "600,00",
            "installment_count": 1,
            "installments": [{
                "seq": 1, "due_date": "2026-02-01", "total_amount_text": "1.000,00",
                "components": [
                    {"component_type_id": self.component_type_id("principal"),
                     "amount_text": "600,00"},  # toplam 1000 ama bileşen 600
                ],
            }],
        }
        with self.assertRaises(ValidationError):
            self.plans.create_debt_plan(data)

    def test_payment_splits_into_principal_and_expense(self):
        _, inst_id = self._create_single_installment_plan()
        txn_id = self.plans.pay_installment(inst_id, self.account_id, "2026-02-01")

        txn = self.txns.get_transaction(txn_id)
        natures = {ln["nature"]: int(ln["amount"]) for ln in txn["lines"]}
        self.assertEqual(natures.get(Nature.PRINCIPAL), 60000)
        self.assertEqual(natures.get(Nature.EXPENSE), 40000)

    def test_payment_decreases_account_balance(self):
        _, inst_id = self._create_single_installment_plan()
        self.plans.pay_installment(inst_id, self.account_id, "2026-02-01")
        balance = int(self.accounts.get_account(self.account_id)["current_balance"])
        self.assertEqual(balance, 900000)  # 10.000 - 1.000 = 9.000,00

    def test_double_payment_rejected(self):
        _, inst_id = self._create_single_installment_plan()
        self.plans.pay_installment(inst_id, self.account_id, "2026-02-01")
        with self.assertRaises(ValidationError):
            self.plans.pay_installment(inst_id, self.account_id, "2026-02-01")

    def test_unpay_reverses_balance_and_status(self):
        _, inst_id = self._create_single_installment_plan()
        self.plans.pay_installment(inst_id, self.account_id, "2026-02-01")
        self.plans.unpay_installment(inst_id)

        balance = int(self.accounts.get_account(self.account_id)["current_balance"])
        self.assertEqual(balance, 1000000)  # 10.000,00 geri geldi
        inst = self.plans.get_installment_for_payment(inst_id)
        self.assertEqual(inst["status"], InstallmentStatus.PLANNED)


if __name__ == "__main__":
    unittest.main()
