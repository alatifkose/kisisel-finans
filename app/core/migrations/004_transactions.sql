CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    txn_date        DATE NOT NULL,
    direction       TEXT NOT NULL,
    total_amount    INTEGER NOT NULL,
    description     TEXT,
    affects_balance INTEGER NOT NULL DEFAULT 1,
    source_type     TEXT NULL,
    source_id       INTEGER NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS transaction_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id),
    nature          TEXT NOT NULL,
    category_id     INTEGER NULL REFERENCES categories(id),
    asset_id        INTEGER NULL REFERENCES assets(id),
    amount          INTEGER NOT NULL,
    note            TEXT,
    deleted_at      TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_txn_account
ON transactions(account_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_txn_date
ON transactions(txn_date)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_line_txn
ON transaction_lines(transaction_id)
WHERE deleted_at IS NULL;
