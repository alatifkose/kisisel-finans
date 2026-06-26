CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS currencies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    symbol      TEXT,
    scale       INTEGER NOT NULL DEFAULT 2,
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    nature      TEXT NOT NULL,
    parent_id   INTEGER NULL REFERENCES categories(id),
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    type        TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS component_types (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    code                    TEXT NOT NULL,
    name                    TEXT NOT NULL,
    nature                  TEXT NOT NULL,
    default_category_id     INTEGER NULL,
    is_active               INTEGER NOT NULL DEFAULT 1,
    deleted_at              TIMESTAMP NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_currency_code
ON currencies(code)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_category_name
ON categories(name, nature)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_asset_name
ON assets(name)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_comptype_code
ON component_types(code)
WHERE deleted_at IS NULL;

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

CREATE TABLE IF NOT EXISTS debt_plans (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id           INTEGER NOT NULL REFERENCES banks(id),
    plan_kind         TEXT NOT NULL,
    name              TEXT NOT NULL,
    principal_amount  INTEGER NOT NULL DEFAULT 0,
    currency_id       INTEGER NOT NULL REFERENCES currencies(id),
    interest_rate     REAL,
    start_date        DATE,
    installment_count INTEGER NOT NULL DEFAULT 0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    note              TEXT,
    source_card_id    INTEGER NULL,
    source_kmh_id     INTEGER NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at        TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS installments (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_plan_id               INTEGER NOT NULL REFERENCES debt_plans(id),
    seq                        INTEGER NOT NULL,
    due_date                   DATE NOT NULL,
    total_amount               INTEGER NOT NULL,
    remaining_principal_after  INTEGER,
    status                     TEXT NOT NULL DEFAULT 'planned',
    paid_transaction_id        INTEGER NULL REFERENCES transactions(id),
    paid_date                  DATE NULL,
    note                       TEXT,
    deleted_at                 TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS installment_components (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    installment_id    INTEGER NOT NULL REFERENCES installments(id),
    component_type_id INTEGER NOT NULL REFERENCES component_types(id),
    amount            INTEGER NOT NULL,
    deleted_at        TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_debt_plan_bank
ON debt_plans(bank_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_debt_plan_currency
ON debt_plans(currency_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_debt_plan_kind
ON debt_plans(plan_kind)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_inst_plan
ON installments(debt_plan_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_inst_due_date
ON installments(due_date)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_comp_inst
ON installment_components(installment_id)
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_installment_plan_seq
ON installments(debt_plan_id, seq)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS credit_cards (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id             INTEGER NOT NULL REFERENCES banks(id),
    name                TEXT NOT NULL,
    currency_id         INTEGER NOT NULL REFERENCES currencies(id),
    card_limit          INTEGER NOT NULL DEFAULT 0,
    cash_advance_limit  INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS audit_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    action       TEXT NOT NULL,
    old_value    TEXT,
    new_value    TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_audit_entity
ON audit_logs(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS ix_audit_created
ON audit_logs(created_at);
