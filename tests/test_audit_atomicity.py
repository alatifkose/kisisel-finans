"""Audit atomikliği: audit yazımı başarısız olursa entity de geri alınmalı.

Refactor öncesi entity ayrı bağlantıda commit ediliyordu; audit hatası entity'yi
geride bırakıyordu. Artık ikisi tek transaction'da.
"""

import unittest

from app.core.exceptions import AppError
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from tests._base import DBTestCase


class _FailingAudit:
    """Her log çağrısında patlayan sahte audit servisi."""

    def log_create(self, *args, **kwargs):
        raise AppError("audit patladı")

    def log_update(self, *args, **kwargs):
        raise AppError("audit patladı")

    def log_delete(self, *args, **kwargs):
        raise AppError("audit patladı")


class AuditAtomicityTests(DBTestCase):
    def test_bank_create_rolls_back_when_audit_fails(self):
        banks = BankService(audit_service=_FailingAudit())
        with self.assertRaises(Exception):
            banks.create_bank("Hayalet Banka")
        # Audit patladıysa banka da kaydedilmemiş olmalı
        names = [b["name"] for b in BankService().list_banks(include_inactive=True)]
        self.assertNotIn("Hayalet Banka", names)

    def test_account_create_rolls_back_when_audit_fails(self):
        bank_id = BankService().create_bank("Gerçek Banka")
        accounts = AccountService(audit_service=_FailingAudit())
        with self.assertRaises(Exception):
            accounts.create_account(bank_id, "Hayalet Hesap", self.currency_id("TRY"), "0")
        names = [a["name"] for a in AccountService().list_accounts(include_inactive=True)]
        self.assertNotIn("Hayalet Hesap", names)


if __name__ == "__main__":
    unittest.main()
