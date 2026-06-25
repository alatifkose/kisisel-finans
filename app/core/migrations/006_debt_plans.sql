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
