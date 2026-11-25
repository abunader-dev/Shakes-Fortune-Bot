CREATE TABLE IF NOT EXISTS pairs (
  code TEXT PRIMARY KEY,
  secret TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
  secret TEXT PRIMARY KEY,
  chat_id INTEGER NOT NULL UNIQUE,
  username TEXT DEFAULT '',
  first_name TEXT DEFAULT '',
  linked_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
  secret TEXT PRIMARY KEY,
  command TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS awaiting_pair (
  chat_id INTEGER PRIMARY KEY,
  expires_at INTEGER NOT NULL
);
