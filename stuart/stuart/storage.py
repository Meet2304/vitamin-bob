import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA busy_timeout=5000;
        CREATE TABLE IF NOT EXISTS missed (
          id TEXT PRIMARY KEY, source_id TEXT UNIQUE, phone TEXT, line_id TEXT,
          received_at TEXT, status TEXT, attempts INTEGER DEFAULT 0, next_at REAL DEFAULT 0,
          decision INTEGER, event_id TEXT);
        CREATE TABLE IF NOT EXISTS calls (
          id TEXT PRIMARY KEY, missed_id TEXT, phone TEXT, line_id TEXT,
          started_at TEXT, ended_at TEXT, reason TEXT, current_action TEXT);
        CREATE TABLE IF NOT EXISTS actions (
          call_id TEXT, action_id TEXT, type TEXT, status TEXT, result TEXT,
          PRIMARY KEY(call_id, action_id));
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, call_id TEXT, payload TEXT, response TEXT,
          attempts INTEGER DEFAULT 0, error TEXT);
        CREATE TABLE IF NOT EXISTS sms (
          id TEXT PRIMARY KEY, request TEXT, priority INTEGER, segments INTEGER,
          status TEXT, line_id TEXT, sent_at TEXT, error TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS incoming (id TEXT PRIMARY KEY, event_id TEXT);
        CREATE TABLE IF NOT EXISTS sync (
          id TEXT PRIMARY KEY, request TEXT, status TEXT, seq INTEGER,
          frames TEXT, attempts INTEGER DEFAULT 0, next_at REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS call_progress (
          id INTEGER PRIMARY KEY AUTOINCREMENT, missed_id TEXT, stage TEXT, at TEXT);
        """)
        sms_columns={r['name'] for r in self.db.execute('PRAGMA table_info(sms)')}
        for column in ('created_at','updated_at'):
            if column not in sms_columns:
                self.db.execute(f'ALTER TABLE sms ADD COLUMN {column} TEXT')
        self.db.execute('UPDATE sms SET created_at=COALESCE(created_at,sent_at,?),updated_at=COALESCE(updated_at,sent_at,?)',(now(),now()))
        self.db.commit()

    def execute(self, sql, params=()):
        with self.lock:
            cursor = self.db.execute(sql, params)
            self.db.commit()
            return cursor.rowcount

    def rows(self, sql, params=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def sequence(self):
        with self.lock:
            row = self.one("SELECT value FROM meta WHERE key='sequence'")
            seq = int(row["value"]) + 1 if row else 1
            self.execute("INSERT OR REPLACE INTO meta VALUES('sequence', ?)", (str(seq),))
            return seq

    def close(self):
        self.db.close()
