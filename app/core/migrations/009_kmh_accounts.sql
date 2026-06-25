CREATE TABLE IF NOT EXISTS kmh_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id             INTEGER NOT NULL REFERENCES banks(id),
    account_id          INTEGER NOT NULL REFERENCES accounts(id),
    name                TEXT NOT NULL,
    kmh_limit           INTEGER NOT NULL DEFAULT 0,
    used_amount         INTEGER NOT NULL DEFAULT 0,
    interest_rate       REAL,
    counts_as_liquidity INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1,
    note                TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_kmh_account_name
ON kmh_accounts(bank_id, name)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_kmh_bank
ON kmh_accounts(bank_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_kmh_account
ON kmh_accounts(account_id)
WHERE deleted_at IS NULL;

ALTER TABLE debt_plans ADD COLUMN source_kmh_id INTEGER NULL;
