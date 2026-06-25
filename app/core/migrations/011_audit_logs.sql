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
