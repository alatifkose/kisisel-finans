CREATE TABLE IF NOT EXISTS banks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    short_name  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    note        TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id          INTEGER NOT NULL REFERENCES banks(id),
    name             TEXT NOT NULL,
    currency_id      INTEGER NOT NULL REFERENCES currencies(id),
    opening_balance  INTEGER NOT NULL DEFAULT 0,
    current_balance  INTEGER NOT NULL DEFAULT 0,
    tracking_mode    TEXT NOT NULL DEFAULT 'ledger',
    is_active        INTEGER NOT NULL DEFAULT 1,
    note             TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at       TIMESTAMP NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_bank_name
ON banks(name)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_account_name
ON accounts(bank_id, name)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_accounts_bank
ON accounts(bank_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_accounts_currency
ON accounts(currency_id)
WHERE deleted_at IS NULL;
