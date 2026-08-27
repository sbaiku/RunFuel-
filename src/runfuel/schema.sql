CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         TEXT    NOT NULL,
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    felt             INTEGER          CHECK (felt IS NULL OR felt BETWEEN 1 AND 5),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
