"""Regresyon: temiz kurulumda migration 007 çakışması yaşanmamalı.

Bu hata daha önce boş veritabanında 'duplicate column name: default_category_id'
ile açılışı çökertiyordu.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.core import database as database_module


class FreshInitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="finans_init_"))
        self._orig_dir = database_module.DB_DIR
        self._orig_path = database_module.DB_PATH
        database_module.DB_DIR = self._tmp
        database_module.DB_PATH = self._tmp / "fresh.db"

    def tearDown(self) -> None:
        database_module.DB_DIR = self._orig_dir
        database_module.DB_PATH = self._orig_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _max_version(self) -> int:
        conn = sqlite3.connect(database_module.DB_PATH)
        try:
            return int(conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0])
        finally:
            conn.close()

    def test_fresh_init_does_not_crash(self):
        database_module.init_database()  # eskiden burada çökerdi

    def test_fresh_init_stamps_latest_version(self):
        database_module.init_database()
        self.assertEqual(self._max_version(), database_module._latest_schema_version())

    def test_init_is_idempotent(self):
        database_module.init_database()
        database_module.init_database()  # ikinci çağrı da sorunsuz olmalı

    def test_component_types_has_default_category_column(self):
        database_module.init_database()
        conn = sqlite3.connect(database_module.DB_PATH)
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(component_types)")]
        finally:
            conn.close()
        self.assertIn("default_category_id", cols)


if __name__ == "__main__":
    unittest.main()
