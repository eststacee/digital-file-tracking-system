import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("data") / "filing_system.db"
VALID_ROLES = {"Admin", "User", "View Only"}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn, table_name):
    return {
        row[1] for row in conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def _add_column_if_missing(conn, table, column, definition):
    if column not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def initialize_database():
    """Create tables and safely add columns to existing prototype databases."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL,
                section TEXT,
                staff_number TEXT NOT NULL UNIQUE,
                password_salt TEXT,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'User',
                oath_acknowledged_at TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE,
                file_name TEXT NOT NULL,
                department TEXT NOT NULL,
                section TEXT,
                barcode TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'AVAILABLE',
                current_holder_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (current_holder_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS file_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                movement_time TEXT NOT NULL,
                remarks TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                notification_type TEXT NOT NULL DEFAULT 'INFO',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_row_id INTEGER,
