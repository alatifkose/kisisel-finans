"""Test altyapısı: her test için geçici, izole bir veritabanı.

Gerçek `app/data/finance.db` dosyasına asla dokunulmaz; modül seviyesindeki
DB yolu geçici bir klasöre yönlendirilir ve test sonunda silinir.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import database as database_module
from app.core.seed import seed_database
from app.repositories.category_repository import CategoryRepository
from app.repositories.component_type_repository import ComponentTypeRepository
from app.repositories.currency_repository import CurrencyRepository


class DBTestCase(unittest.TestCase):
    """Temiz bir DB kurup seed eden temel test sınıfı."""

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="finans_test_"))
        self._orig_dir = database_module.DB_DIR
        self._orig_path = database_module.DB_PATH
        database_module.DB_DIR = self._tmp
        database_module.DB_PATH = self._tmp / "test.db"

        database_module.init_database()
        seed_database()

    def tearDown(self) -> None:
        database_module.DB_DIR = self._orig_dir
        database_module.DB_PATH = self._orig_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    # --- seed verisi yardımcıları ---

    def currency_id(self, code: str) -> int:
        for row in CurrencyRepository().list_currencies():
            if row["code"] == code:
                return int(row["id"])
        raise AssertionError(f"Para birimi bulunamadı: {code}")

    def category_id(self, name: str) -> int:
        for row in CategoryRepository().list_categories():
            if row["name"] == name:
                return int(row["id"])
        raise AssertionError(f"Kategori bulunamadı: {name}")

    def component_type_id(self, code: str) -> int:
        for row in ComponentTypeRepository().list_component_types():
            if row["code"] == code:
                return int(row["id"])
        raise AssertionError(f"Bileşen tipi bulunamadı: {code}")
