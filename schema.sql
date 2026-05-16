-- schema.sql

CREATE TABLE tasks (
            id               TEXT PRIMARY KEY,
            text             TEXT NOT NULL,
            category         TEXT NOT NULL,
            priority         TEXT,
            status           TEXT NOT NULL DEFAULT 'pending',
            created_at       TEXT NOT NULL,
            next_reminder_at TEXT,
            snoozed_until    TEXT
        );

