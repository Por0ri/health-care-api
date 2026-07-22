PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    pw TEXT NOT NULL,
    name TEXT NOT NULL,
    birth TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
    admin_id TEXT PRIMARY KEY,
    pw TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,
    height REAL NOT NULL CHECK (height > 0),
    weight REAL NOT NULL CHECK (weight > 0),
    systolic INTEGER NOT NULL CHECK (systolic > 0),
    diastolic INTEGER NOT NULL CHECK (diastolic > 0),
    blood_sugar REAL NOT NULL CHECK (blood_sugar >= 0),
    memo TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE (user_id, date)
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
    account_id TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_measurements_user_date
    ON measurements(user_id, date);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
    ON sessions(expires_at);
