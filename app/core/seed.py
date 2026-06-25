"""Başlangıç referans verisi."""

from __future__ import annotations

import sqlite3

from app.core.database import get_connection
from app.core.exceptions import AppError

SEED_CURRENCIES = [
    ("TRY", "₺", 2),
    ("USD", "$", 2),
    ("EUR", "€", 2),
    ("XAU", "gr", 3),
]

SEED_COMPONENT_TYPES = [
    ("principal", "Anapara", "principal"),
    ("interest", "Faiz", "expense"),
    ("kkdf", "KKDF", "expense"),
    ("bsmv", "BSMV", "expense"),
    ("fund", "Fon", "expense"),
    ("tax", "Vergi", "expense"),
    ("life_ins", "Hayat sigortası", "expense"),
    ("fee", "Masraf/ücret", "expense"),
]

SEED_CATEGORIES = [
    ("Faiz gideri", "expense"),
    ("Sigorta", "expense"),
    ("Yakıt", "expense"),
    ("Kira", "expense"),
    ("Aidat", "expense"),
    ("Elektrik", "expense"),
    ("Su", "expense"),
    ("Tamir", "cost"),
    ("Onarım", "cost"),
    ("Maaş", "income"),
]

SEED_ASSETS = [
    ("Genel", "other"),
    ("Twingo", "vehicle"),
    ("Ev", "property"),
]


class SeedError(AppError):
    """Seed işlemi hatası."""


def _exists_active(conn: sqlite3.Connection, table: str, where: str, params: tuple) -> bool:
    query = f"SELECT 1 FROM {table} WHERE deleted_at IS NULL AND {where} LIMIT 1"
    return conn.execute(query, params).fetchone() is not None


def _insert_or_skip(
    conn: sqlite3.Connection,
    table: str,
    exists_where: str,
    exists_params: tuple,
    insert_sql: str,
    insert_params: tuple,
    duplicate_message: str,
) -> None:
    if _exists_active(conn, table, exists_where, exists_params):
        return
    try:
        conn.execute(insert_sql, insert_params)
    except sqlite3.IntegrityError as exc:
        raise SeedError(duplicate_message) from exc


def seed_database() -> None:
    """Başlangıç referans verilerini yalnızca eksik kayıtlar için ekle."""
    with get_connection() as conn:
        for code, symbol, scale in SEED_CURRENCIES:
            _insert_or_skip(
                conn,
                "currencies",
                "code = ?",
                (code,),
                "INSERT INTO currencies (code, symbol, scale) VALUES (?, ?, ?)",
                (code, symbol, scale),
                f"Para birimi eklenemedi: '{code}' zaten mevcut veya benzersiz kısıt ihlali.",
            )

        for code, name, nature in SEED_COMPONENT_TYPES:
            _insert_or_skip(
                conn,
                "component_types",
                "code = ?",
                (code,),
                "INSERT INTO component_types (code, name, nature) VALUES (?, ?, ?)",
                (code, name, nature),
                f"Bileşen tipi eklenemedi: '{code}' zaten mevcut veya benzersiz kısıt ihlali.",
            )

        for name, nature in SEED_CATEGORIES:
            _insert_or_skip(
                conn,
                "categories",
                "name = ? AND nature = ?",
                (name, nature),
                "INSERT INTO categories (name, nature) VALUES (?, ?)",
                (name, nature),
                f"Kategori eklenemedi: '{name}' ({nature}) zaten mevcut veya benzersiz kısıt ihlali.",
            )

        for name, asset_type in SEED_ASSETS:
            _insert_or_skip(
                conn,
                "assets",
                "name = ?",
                (name,),
                "INSERT INTO assets (name, type) VALUES (?, ?)",
                (name, asset_type),
                f"Varlık eklenemedi: '{name}' zaten mevcut veya benzersiz kısıt ihlali.",
            )

        _seed_component_type_default_categories(conn)


def _seed_component_type_default_categories(conn: sqlite3.Connection) -> None:
    """Gider bileşen tiplerine varsayılan kategori eşlemesi uygula."""
    mappings = {
        "interest": "Faiz gideri",
        "kkdf": "Faiz gideri",
        "bsmv": "Faiz gideri",
        "fund": "Faiz gideri",
        "tax": "Faiz gideri",
        "fee": "Faiz gideri",
        "life_ins": "Sigorta",
    }
    for code, category_name in mappings.items():
        conn.execute(
            """
            UPDATE component_types
            SET default_category_id = (
                SELECT id FROM categories
                WHERE name = ? AND nature = 'expense' AND deleted_at IS NULL
                LIMIT 1
            )
            WHERE code = ?
              AND nature = 'expense'
              AND deleted_at IS NULL
              AND default_category_id IS NULL
            """,
            (category_name, code),
        )
