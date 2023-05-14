-- drop tables


-- tables

-- Table: users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_uid INTEGER UNIQUE NOT NULL,
    username TEXT NOT NULL
);

-- Table: sub_durations
CREATE TABLE sub_durations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    duration INTEGER CHECK(duration > 0) NOT NULL,
    unit TEXT CHECK(unit IN ('day', 'month')) NOT NULL 
);

-- Table: subscriptions
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Table: unique_codes
CREATE TABLE unique_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    redeemed BOOLEAN CHECK(redeemed IN (0, 1)) NOT NULL DEFAULT 0,
    expiry_date TEXT NOT NULL,
    duration_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    FOREIGN KEY (duration_id) REFERENCES sub_durations (id),
    FOREIGN KEY (admin_id) REFERENCES users (id)
);

-- Table: redeemed_codes
CREATE TABLE redeemed_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redemption_date text NOT NULL,
    unique_code_id INTEGER UNIQUE NOT NULL,
    subscription_id INTEGER NOT NULL,
    FOREIGN KEY (unique_code_id) REFERENCES unique_codes (id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
);

-- Table: grants
CREATE TABLE grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_date TEXT NOT NULL,
    action_type TEXT CHECK(action_type IN ('grant', 'extend')) NOT NULL,
    original_end_date TEXT,
    new_end_date TEXT NOT NULL,
    duration_id INTEGER NOT NULL,
    subscription_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (duration_id) REFERENCES sub_durations (id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id),
    FOREIGN KEY (admin_id) REFERENCES users (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Table: revokes
CREATE TABLE revokes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revoke_date TEXT NOT NULL,
    action_type TEXT CHECK(action_type IN ('revoke', 'reduce')) NOT NULL,
    original_end_date TEXT NOT NULL,
    new_end_date TEXT,
    duration_id INTEGER NOT NULL,
    subscription_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (duration_id) REFERENCES sub_durations (id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id),
    FOREIGN KEY (admin_id) REFERENCES users (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);


-- Inserting Base Data

INSERT INTO sub_durations (duration, unit) VALUES (1, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (3, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (7, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (14, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (1, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (3, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (6, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (12, 'month');

-- End of file.