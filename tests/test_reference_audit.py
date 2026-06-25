"""reference_service artık mutasyonları audit'e yazıyor (plan §8.17) ve atomik."""

import unittest

from app.core.exceptions import AppError
from app.services.audit_service import AuditService
from app.services.reference_service import ReferenceService
from tests._base import DBTestCase


class _FailingAudit:
    def log_create(self, *a, **k):
        raise AppError("audit patladı")

    def log_update(self, *a, **k):
        raise AppError("audit patladı")

    def log_delete(self, *a, **k):
        raise AppError("audit patladı")


class ReferenceAuditTests(DBTestCase):
    def setUp(self):
        super().setUp()
        self.ref = ReferenceService()
        self.audit = AuditService()

    def test_create_category_writes_audit(self):
        cat_id = self.ref.create_category("Test Kategori", "expense")
        logs = self.audit.list_logs_by_entity("category", cat_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["action"], "create")

    def test_create_currency_writes_audit(self):
        cur_id = self.ref.create_currency("GBP", "£", 2)
        logs = self.audit.list_logs_by_entity("currency", cur_id)
        self.assertTrue(any(l["action"] == "create" for l in logs))

    def test_delete_asset_writes_audit(self):
        asset_id = self.ref.create_asset("Test Varlık", "other")
        self.ref.delete_asset(asset_id)
        actions = {l["action"] for l in self.audit.list_logs_by_entity("asset", asset_id)}
        self.assertIn("delete", actions)

    def test_create_rolls_back_when_audit_fails(self):
        ref = ReferenceService(audit_service=_FailingAudit())
        with self.assertRaises(Exception):
            ref.create_category("Hayalet Kategori", "expense")
        names = [c["name"] for c in ReferenceService().list_categories(include_inactive=True)]
        self.assertNotIn("Hayalet Kategori", names)


if __name__ == "__main__":
    unittest.main()
