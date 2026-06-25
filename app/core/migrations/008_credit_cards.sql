CREATE TABLE IF NOT EXISTS credit_cards (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id             INTEGER NOT NULL REFERENCES banks(id),
    name                TEXT NOT NULL,
    currency_id         INTEGER NOT NULL REFERENCES currencies(id),
    card_limit          INTEGER NOT NULL DEFAULT 0,
    statement_day       INTEGER,
    due_day             INTEGER,
    counts_as_liquidity INTEGER NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1,
    note                TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS card_statements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_card_id  INTEGER NOT NULL REFERENCES credit_cards(id),
    statement_date  DATE NOT NULL,
    statement_debt  INTEGER NOT NULL DEFAULT 0,
    min_payment     INTEGER NOT NULL DEFAULT 0,
    due_date        DATE,
    available_limit INTEGER,
    note            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_credit_card_name
ON credit_cards(bank_id, name)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_credit_cards_bank
ON credit_cards(bank_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_credit_cards_currency
ON credit_cards(currency_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_card_statements_card
ON card_statements(credit_card_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_card_statements_date
ON card_statements(statement_date)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_card_statement_date
ON card_statements(credit_card_id, statement_date)
WHERE deleted_at IS NULL;

ALTER TABLE debt_plans ADD COLUMN source_card_id INTEGER NULL;
