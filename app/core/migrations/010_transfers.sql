CREATE TABLE IF NOT EXISTS transfers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id  INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id    INTEGER NOT NULL REFERENCES accounts(id),
    from_amount      INTEGER NOT NULL,
    from_currency_id INTEGER NOT NULL REFERENCES currencies(id),
    to_amount        INTEGER NOT NULL,
    to_currency_id   INTEGER NOT NULL REFERENCES currencies(id),
    exchange_rate    REAL NULL,
    transfer_date    DATE NOT NULL,
    description      TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at       TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_transfers_from_account
ON transfers(from_account_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_transfers_to_account
ON transfers(to_account_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_transfers_date
ON transfers(transfer_date)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_transfers_from_currency
ON transfers(from_currency_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_transfers_to_currency
ON transfers(to_currency_id)
WHERE deleted_at IS NULL;
