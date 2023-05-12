-- tables

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_uid INTEGER UNIQUE NOT NULL,
    username TEXT NOT NULL
);

-- Table: sub_types
CREATE TABLE IF NOT EXISTS sub_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- Table: sub_durations
CREATE TABLE IF NOT EXISTS sub_durations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    duration INTEGER NOT NULL,
    unit TEXT NOT NULL
);

-- Table: subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    sub_type_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (sub_type_id) REFERENCES sub_types (id)
);

-- Table: unique_codes
CREATE TABLE IF NOT EXISTS unique_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    redeemed BOOLEAN NOT NULL DEFAULT 0,
    expiry_date TEXT NOT NULL,
    duration_id INTEGER NOT NULL,
    creator_uid INTEGER NOT NULL,
    FOREIGN KEY (duration_id) REFERENCES sub_durations (id),
    FOREIGN KEY (creator_uid) REFERENCES users (id)
);

-- Table: redeemed_codes
CREATE TABLE IF NOT EXISTS redeemed_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redemption_date text NOT NULL,
    unique_code_id INTEGER UNIQUE NOT NULL,
    subscription_id INTEGER NOT NULL,
    FOREIGN KEY (unique_code_id) REFERENCES unique_codes (id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
);

-- Table: manual_ubscriptions
CREATE TABLE IF NOT EXISTS manual_subs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creation_date TEXT NOT NULL,
    duration_id INTEGER NOT NULL,
    creator_uid INTEGER NOT NULL,
    subscription_id INTEGER NOT NULL,
    FOREIGN KEY (duration_id) REFERENCES sub_durations (id),
    FOREIGN KEY (creator_uid) REFERENCES users (id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
);



-- Inserting Base Data

INSERT INTO sub_types (name) VALUES ('Code');
INSERT INTO sub_types (name) VALUES ('Manual');

INSERT INTO sub_durations (duration, unit) VALUES (1, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (3, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (7, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (14, 'day');
INSERT INTO sub_durations (duration, unit) VALUES (1, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (3, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (6, 'month');
INSERT INTO sub_durations (duration, unit) VALUES (12, 'month');

-- End of file.