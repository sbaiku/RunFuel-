CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         TEXT    NOT NULL,
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
