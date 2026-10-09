
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("data") / "filing_system.db"


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, table, column, definition):
    if column not in _column_names(conn, table):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def initialize_database():
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
                FOREIGN KEY (current_holder_id)
                    REFERENCES users(id)
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
            """
        )

        # Add newer columns to an older prototype database.
        _add_column_if_missing(conn, "users", "section", "TEXT")
        _add_column_if_missing(conn, "users", "password_salt", "TEXT")
        _add_column_if_missing(conn, "users", "password_hash", "TEXT")
        _add_column_if_missing(
            conn, "users", "role", "TEXT NOT NULL DEFAULT 'User'"
        )
        _add_column_if_missing(
            conn, "users", "oath_acknowledged_at", "TEXT"
        )
        _add_column_if_missing(
            conn, "users", "active", "INTEGER NOT NULL DEFAULT 1"
        )

        _add_column_if_missing(conn, "files", "file_id", "TEXT")
        _add_column_if_missing(conn, "files", "section", "TEXT")
        _add_column_if_missing(conn, "files", "barcode", "TEXT")

        # Give older file records generated IDs and barcodes.
        legacy_rows = conn.execute(
            "SELECT id, file_id, barcode FROM files ORDER BY id"
        ).fetchall()

        for row in legacy_rows:
            current = conn.execute(
                "SELECT file_id, barcode FROM files WHERE id = ?",
                (row["id"],),
            ).fetchone()

            generated_id = (
                current["file_id"]
                if current["file_id"]
                else f"DFS-{int(row['id']):06d}"
            )

            conn.execute(
                "UPDATE files SET file_id = ?, barcode = ? WHERE id = ?",
                (generated_id, generated_id, row["id"]),
            )

        conn.commit()
    finally:
        conn.close()


def _hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )

    return salt.hex(), password_hash.hex()


def _verify_password(password, salt_hex, stored_hash):
    _, candidate = _hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, stored_hash)


def has_users():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM users LIMIT 1"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def create_first_admin(
    name,
    email,
    department,
    section,
    staff_number,
    password,
):
    if has_users():
        raise ValueError(
            "An initial administrator already exists."
        )

    return add_user(
        name=name,
        email=email,
        department=department,
        section=section,
        staff_number=staff_number,
        role="Admin",
        password=password,
    )


def add_user(
    name,
    email,
    department,
    section,
    staff_number,
    role="User",
    password="",
):
    role = role.strip().title()

    if role not in {"Admin", "User", "View Only"}:
        raise ValueError(
            "Role must be Admin, User, or View Only."
        )

    if not password:
        raise ValueError("Password is required.")

    salt, password_hash = _hash_password(password)
    now = _utc_now()

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (
                name, email, department, section, staff_number,
                password_salt, password_hash, role, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                email.strip().lower(),
                department.strip(),
                (section or "").strip() or None,
                staff_number.strip().upper(),
                salt,
                password_hash,
                role,
                now,
            ),
        )

        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    finally:
        conn.close()


def get_users(active_only=False):
    conn = get_connection()
    try:
        query = "SELECT * FROM users"

        if active_only:
            query += " WHERE active = 1"

        query += " ORDER BY name COLLATE NOCASE"

        return [
            dict(row)
            for row in conn.execute(query).fetchall()
        ]
    finally:
        conn.close()


def authenticate_user(staff_number, password):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM users
            WHERE staff_number = ? AND active = 1
            """,
            (staff_number.strip().upper(),),
        ).fetchone()

        if (
            not row
            or not row["password_hash"]
            or not row["password_salt"]
        ):
            return None

        if not _verify_password(
            password,
            row["password_salt"],
            row["password_hash"],
        ):
            return None

        return dict(row)
    finally:
        conn.close()


def _next_file_id(conn):
    row = conn.execute(
        "SELECT MAX(id) AS max_id FROM files"
    ).fetchone()

    next_number = int(row["max_id"] or 0) + 1
    return f"DFS-{next_number:06d}"


def add_item(file_name, department, section=None):
    conn = get_connection()
    try:
        file_id = _next_file_id(conn)
        now = _utc_now()

        conn.execute(
            """
            INSERT INTO files (
                file_id, file_name, department, section, barcode,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'AVAILABLE', ?)
            """,
            (
                file_id,
                file_name.strip(),
                department.strip(),
                (section or "").strip() or None,
                file_id,
                now,
            ),
        )

        conn.commit()
        return file_id
    finally:
        conn.close()


def get_items(status=None):
    conn = get_connection()
    try:
        query = """
            SELECT
                f.*,
                u.name AS current_holder_name,
                u.staff_number AS current_holder_staff_number
            FROM files f
            LEFT JOIN users u ON f.current_holder_id = u.id
        """

        params = []

        if status:
            query += " WHERE f.status = ?"
            params.append(status)

        query += " ORDER BY f.id DESC"

        return [
            dict(row)
            for row in conn.execute(query, params).fetchall()
        ]
    finally:
        conn.close()


def get_files(status=None):
    return get_items(status=status)


def find_item(identifier):
    value = (identifier or "").strip().upper()

    if not value:
        return None

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                f.*,
                u.name AS current_holder_name,
                u.staff_number AS current_holder_staff_number
            FROM files f
            LEFT JOIN users u ON f.current_holder_id = u.id
            WHERE UPPER(f.barcode) = ?
               OR UPPER(f.file_id) = ?
            LIMIT 1
            """,
            (value, value),
        ).fetchone()

        return dict(row) if row else None
    finally:
        conn.close()


def _notify(
    conn,
    user_id,
    title,
    message,
    kind="INFO",
):
    conn.execute(
        """
        INSERT INTO notifications (
            user_id, title, message, notification_type, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, title, message, kind, _utc_now()),
    )


def issue_item(item_id, user_id, remarks=""):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, file_id, file_name, status, current_holder_id
            FROM files WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        if not row:
            raise ValueError("File not found.")

        if (
            row["status"] != "AVAILABLE"
            or row["current_holder_id"] is not None
        ):
            raise ValueError("This file is already out.")

        conn.execute(
            """
            UPDATE files
            SET status = 'OUT', current_holder_id = ?
            WHERE id = ?
            """,
            (user_id, item_id),
        )

        conn.execute(
            """
            INSERT INTO file_movements (
                file_id, user_id, action, movement_time, remarks
            )
            VALUES (?, ?, 'ISSUED', ?, ?)
            """,
            (
                item_id,
                user_id,
                _utc_now(),
                remarks.strip() or None,
            ),
        )

        _notify(
            conn,
            user_id,
            "File issued successfully",
            f"{row['file_id']} - {row['file_name']} "
            "has been issued to you.",
            "ISSUE",
        )

        conn.commit()
    finally:
        conn.close()


def return_item(item_id, user_id, remarks=""):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, file_id, file_name, status, current_holder_id
            FROM files WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        if not row:
            raise ValueError("File not found.")

        if (
            row["status"] != "OUT"
            or row["current_holder_id"] is None
        ):
            raise ValueError("This file is already available.")

        if int(row["current_holder_id"]) != int(user_id):
            raise PermissionError(
                "Only the current holder can return this file."
            )

        conn.execute(
            """
            UPDATE files
            SET status = 'AVAILABLE', current_holder_id = NULL
            WHERE id = ?
            """,
            (item_id,),
        )

        conn.execute(
            """
            INSERT INTO file_movements (
                file_id, user_id, action, movement_time, remarks
            )
            VALUES (?, ?, 'RETURNED', ?, ?)
            """,
            (
                item_id,
                user_id,
                _utc_now(),
                remarks.strip() or None,
            ),
        )

        _notify(
            conn,
            user_id,
            "File returned successfully",
            f"{row['file_id']} - {row['file_name']} "
            "has been returned and is now available.",
            "RETURN",
        )

        conn.commit()
    finally:
        conn.close()


def get_movements(file_id=None):
    conn = get_connection()
    try:
        query = """
            SELECT
                m.id,
                f.file_id AS system_file_id,
                f.file_name,
                u.name AS user_name,
                u.staff_number,
                m.action,
                m.movement_time,
                m.remarks
            FROM file_movements m
            JOIN files f ON m.file_id = f.id
            JOIN users u ON m.user_id = u.id
        """

        params = []

        if file_id is not None:
            query += " WHERE m.file_id = ?"
            params.append(file_id)

        query += " ORDER BY m.id DESC"

        return [
            dict(row)
            for row in conn.execute(query, params).fetchall()
        ]
    finally:
        conn.close()


def get_notifications(user_id, include_read=True):
    conn = get_connection()
    try:
        query = """
            SELECT
                id, title, message, notification_type,
                is_read, created_at
            FROM notifications
            WHERE user_id = ? OR user_id IS NULL
        """

        params = [user_id]

        if not include_read:
            query += " AND is_read = 0"

        query += " ORDER BY id DESC LIMIT 100"

        return [
            dict(row)
            for row in conn.execute(query, params).fetchall()
        ]
    finally:
        conn.close()


def mark_notifications_read(user_id):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE notifications SET is_read = 1
            WHERE user_id = ? OR user_id IS NULL
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def acknowledge_oath(user_id):
    conn = get_connection()
    try:
        timestamp = _utc_now()

        conn.execute(
            """
            UPDATE users
            SET oath_acknowledged_at = ?
            WHERE id = ?
            """,
            (timestamp, user_id),
        )

        _notify(
            conn,
            user_id,
            "Oath acknowledged",
            "Your Oath & Responsibilities acknowledgement "
            "has been recorded.",
            "OATH",
        )

        conn.commit()
        return timestamp
    finally:
        conn.close()
