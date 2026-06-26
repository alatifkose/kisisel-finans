-- Kredi kartı tekil hareketleri (alışveriş / nakit avans / ödeme / ücret / faiz).
-- Taksitli işlemler burada DEĞİL, debt_plans'ta (source_card_id) yaşar.
CREATE TABLE IF NOT EXISTS card_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_card_id  INTEGER NOT NULL REFERENCES credit_cards(id),
    txn_date        DATE NOT NULL,
    entry_type      TEXT NOT NULL,   -- purchase|cash_advance|payment|fee|interest
    amount          INTEGER NOT NULL,
    category_id     INTEGER NULL REFERENCES categories(id),
    description     TEXT,
    note            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_card_entries_card
ON card_entries(credit_card_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_card_entries_date
ON card_entries(txn_date)
WHERE deleted_at IS NULL;
