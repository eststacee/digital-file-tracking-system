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
                file_id TEXT,
                file_name TEXT,
                actor_user_id INTEGER,
                actor_name TEXT NOT NULL,
                action TEXT NOT NULL,
                previous_value TEXT,
                new_value TEXT,
                outcome TEXT NOT NULL DEFAULT 'SUCCESS',
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (file_row_id) REFERENCES files(id),
                FOREIGN KEY (actor_user_id) REFERENCES users(id)
            );

            CREATE TRIGGER IF NOT EXISTS audit_trail_prevent_update
            BEFORE UPDATE ON audit_trail
            BEGIN
                SELECT RAISE(ABORT, 'Audit trail is read-only');
            END;

            CREATE TRIGGER IF NOT EXISTS audit_trail_prevent_delete
            BEFORE DELETE ON audit_trail
            BEGIN
                SELECT RAISE(ABORT, 'Audit trail is read-only');
            END;
            """
        )

        # Migrate older databases without dropping existing records.
        migrations = [
            ("users", "section", "TEXT"),
            ("users", "password_salt", "TEXT"),
            ("users", "password_hash", "TEXT"),
            ("users", "role", "TEXT NOT NULL DEFAULT 'User'"),
            ("users", "oath_acknowledged_at", "TEXT"),
            ("users", "active", "INTEGER NOT NULL DEFAULT 1"),
            ("files", "file_id", "TEXT"),
            ("files", "section", "TEXT"),
            ("files", "barcode", "TEXT"),
            ("files", "created_by", "INTEGER REFERENCES users(id)"),
            ("files", "approval_status", "TEXT NOT NULL DEFAULT 'APPROVED'"),
            ("files", "approved_by", "INTEGER REFERENCES users(id)"),
            ("files", "approved_at", "TEXT"),
            ("files", "updated_at", "TEXT"),
            ("files", "updated_by", "INTEGER REFERENCES users(id)"),
            ("files", "deleted_at", "TEXT"),
            ("files", "deleted_by", "INTEGER REFERENCES users(id)"),
        ]
        for table, column, definition in migrations:
            _add_column_if_missing(conn, table, column, definition)

        # Give older file records IDs/barcodes and retain them as approved legacy records.
        legacy_rows = conn.execute(
            "SELECT id, file_id, barcode FROM files ORDER BY id"
        ).fetchall()
        for row in legacy_rows:
            generated_id = row["file_id"] or f"DFS-{int(row['id']):06d}"
            generated_barcode = row["barcode"] or generated_id
            conn.execute(
                """
                UPDATE files
                SET file_id = ?, barcode = ?,
                    approval_status = COALESCE(approval_status, 'APPROVED')
                WHERE id = ?
                """,
                (generated_id, generated_barcode, row["id"]),
            )

        conn.commit()
    finally:
        conn.close()


def _hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 200_000
    )
    return salt.hex(), password_hash.hex()


def _verify_password(password, salt_hex, stored_hash):
    _, candidate = _hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, stored_hash)


def _user_id(user):
    if isinstance(user, dict):
        value = user.get("id")
    else:
        value = user
    if value is None:
        raise PermissionError("A logged-in user is required for this action.")
    return int(value)


def _get_user(conn, user):
    uid = _user_id(user)
    row = conn.execute(
        "SELECT * FROM users WHERE id = ? AND active = 1", (uid,)
    ).fetchone()
    if not row:
        raise PermissionError("User is not registered or is inactive.")
    return dict(row)


def _is_admin(user):
    return str(user.get("role", "")).strip().lower() == "admin"


def _can_view_file(user, file_row):
    """Option C: section visibility, or department fallback for sectionless users."""
    if _is_admin(user):
        return True
    user_department = (user.get("department") or "").strip().casefold()
    user_section = (user.get("section") or "").strip().casefold()
    file_department = (file_row.get("department") or "").strip().casefold()
    file_section = (file_row.get("section") or "").strip().casefold()

    if not user_department or user_department != file_department:
        return False
    if user_section:
        return bool(file_section) and user_section == file_section
    return True


def _notify(conn, user_id, title, message, kind="INFO"):
    conn.execute(
        """
        INSERT INTO notifications
            (user_id, title, message, notification_type, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, title, message, kind, _utc_now()),
    )


def _notify_user(conn, user_id, title, message, kind="INFO"):
    _notify(conn, int(user_id), title, message, kind)


def _notify_admins(conn, title, message, kind="ADMIN_ALERT"):
    admins = conn.execute(
        "SELECT id FROM users WHERE active = 1 AND LOWER(role) = 'admin'"
    ).fetchall()
    for admin in admins:
        _notify(conn, admin["id"], title, message, kind)


def _broadcast(conn, title, message, kind="INFO"):
    """Create an individual notification for every active registered user."""
    users = conn.execute("SELECT id FROM users WHERE active = 1").fetchall()
    for user in users:
        _notify(conn, user["id"], title, message, kind)


def _audit(conn, file_row, actor, action, previous_value=None,
           new_value=None, outcome="SUCCESS", details=None):
    actor_dict = _get_user(conn, actor)
    file_row = dict(file_row) if file_row else {}
    conn.execute(
        """
        INSERT INTO audit_trail (
            file_row_id, file_id, file_name, actor_user_id, actor_name,
            action, previous_value, new_value, outcome, details, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_row.get("id"), file_row.get("file_id"),
            file_row.get("file_name"), actor_dict["id"], actor_dict["name"],
            action, previous_value, new_value, outcome, details, _utc_now(),
        ),
    )


def has_users():
    conn = get_connection()
    try:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    finally:
        conn.close()


def create_first_admin(name, email, department, section, staff_number, password):
    if has_users():
        raise ValueError("An initial administrator already exists.")
    return add_user(
        name=name, email=email, department=department, section=section,
        staff_number=staff_number, role="Admin", password=password
    )


def add_user(name, email, department, section, staff_number,
             role="User", password=""):
    role = role.strip().title()
    if role not in VALID_ROLES:
        raise ValueError("Role must be Admin, User, or View Only.")
    if not password:
        raise ValueError("Password is required.")

    salt, password_hash = _hash_password(password)
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (
                name, email, department, section, staff_number,
                password_salt, password_hash, role, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(), email.strip().lower(), department.strip(),
                (section or "").strip() or None, staff_number.strip().upper(),
                salt, password_hash, role, _utc_now(),
            ),
        )
        uid = cursor.lastrowid
        _broadcast(
            conn, "New user registered",
            f"{name.strip()} has been added to the Digital Filing System.",
            "USER",
        )
        conn.commit()
        return uid
    finally:
        conn.close()


def get_users(active_only=False):
    conn = get_connection()
    try:
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name COLLATE NOCASE"
        return [dict(row) for row in conn.execute(query).fetchall()]
    finally:
        conn.close()


def authenticate_user(staff_number, password):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE staff_number = ? AND active = 1",
            (staff_number.strip().upper(),),
        ).fetchone()
        if (not row or not row["password_hash"] or not row["password_salt"]):
            return None
        if not _verify_password(password, row["password_salt"], row["password_hash"]):
            return None
        return dict(row)
    finally:
        conn.close()


def _next_file_id(conn):
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM files").fetchone()
    return f"DFS-{int(row['max_id'] or 0) + 1:06d}"


def add_item(file_name, department, section=None, created_by=None):
    """
    Register a file. Pass the logged-in user ID/dict as created_by.
    User-created files require Admin approval. A missing creator is rejected
    to prevent records without accountable ownership.
    """
    conn = get_connection()
    try:
        actor = _get_user(conn, created_by)
        if actor["role"] == "View Only":
            raise PermissionError("View Only users cannot create files.")

        file_name = (file_name or "").strip()
        department = (department or "").strip()
        section = (section or "").strip() or None
        if not file_name or not department:
            raise ValueError("File name and department are required.")

        # Users may register files only for their own department/section.
        if not _is_admin(actor):
            if department.casefold() != actor["department"].strip().casefold():
                raise PermissionError("You can only create files for your department.")
            actor_section = (actor.get("section") or "").strip()
            if actor_section and (section or "").casefold() != actor_section.casefold():
                raise PermissionError("You can only create files for your own section.")

        file_id = _next_file_id(conn)
        now = _utc_now()
        approval_status = "APPROVED" if _is_admin(actor) else "PENDING"
        cursor = conn.execute(
            """
            INSERT INTO files (
                file_id, file_name, department, section, barcode, status,
                created_at, created_by, approval_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'AVAILABLE', ?, ?, ?, ?)
            """,
            (file_id, file_name, department, section, file_id, now,
             actor["id"], approval_status, now),
        )
        file_row = conn.execute(
            "SELECT * FROM files WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        _audit(conn, file_row, actor, "FILE_CREATED",
               new_value=f"{file_name} | {department} | {section or 'No section'}")
        _notify_admins(
            conn, "New file created",
            f"{file_id} - {file_name} was created by {actor['name']}. "
            f"Approval status: {approval_status}.",
        )
        _broadcast(
            conn, "File created",
            f"{file_id} - {file_name} was registered. Status: {approval_status}.",
            "FILE_CREATED",
        )
        conn.commit()
        return file_id
    finally:
        conn.close()


def _file_query():
    return """
        SELECT f.*, creator.name AS creator_name,
               holder.name AS current_holder_name,
               holder.staff_number AS current_holder_staff_number
        FROM files f
        LEFT JOIN users creator ON f.created_by = creator.id
        LEFT JOIN users holder ON f.current_holder_id = holder.id
    """


def get_items(status=None, current_user=None, include_deleted=False):
    """Return only files visible to current_user under Option C."""
    conn = get_connection()
    try:
        actor = _get_user(conn, current_user)
        query = _file_query() + " WHERE 1 = 1"
        params = []
        if not include_deleted:
            query += " AND f.deleted_at IS NULL"
        if status:
            query += " AND f.status = ?"
            params.append(status)
        rows = [dict(r) for r in conn.execute(query + " ORDER BY f.id DESC", params).fetchall()]
        visible = []
        for row in rows:
            if _can_view_file(actor, row):
                visible.append(row)
        return visible
    finally:
        conn.close()


def get_files(status=None, current_user=None, include_deleted=False):
    return get_items(status=status, current_user=current_user,
                     include_deleted=include_deleted)


def find_item(identifier, current_user=None):
    value = (identifier or "").strip().upper()
    if not value:
        return None
    conn = get_connection()
    try:
        actor = _get_user(conn, current_user)
        row = conn.execute(
            _file_query() + """
                WHERE (UPPER(f.barcode) = ? OR UPPER(f.file_id) = ?)
                  AND f.deleted_at IS NULL
                LIMIT 1
            """,
            (value, value),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        if not _can_view_file(actor, item):
            # Do not reveal whether an inaccessible file exists.
            return None
        return item
    finally:
        conn.close()


def modify_item(item_id, user_id, updates):
    """Modify an owned file only; changes are audited and Admins are alerted."""
    allowed = {"file_name", "department", "section"}
    if not isinstance(updates, dict) or not updates:
        raise ValueError("Provide at least one file field to update.")
    if set(updates) - allowed:
        raise ValueError("Only file name, department and section can be modified.")

    conn = get_connection()
    try:
        actor = _get_user(conn, user_id)
        if actor["role"] == "View Only":
            raise PermissionError("View Only users cannot modify files.")
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND deleted_at IS NULL", (item_id,)
        ).fetchone()
        if not row:
            raise ValueError("File not found.")
        old = dict(row)
        if not _is_admin(actor) and int(old.get("created_by") or -1) != actor["id"]:
            raise PermissionError("You can only modify files you created.")
        if not _is_admin(actor):
            dept = updates.get("department", old["department"])
            sect = updates.get("section", old["section"])
            if dept.strip().casefold() != actor["department"].strip().casefold():
                raise PermissionError("You cannot move a file to another department.")
            actor_section = (actor.get("section") or "").strip()
            if actor_section and (sect or "").strip().casefold() != actor_section.casefold():
                raise PermissionError("You cannot move a file to another section.")

        new_values = {
            "file_name": (updates.get("file_name", old["file_name"]) or "").strip(),
            "department": (updates.get("department", old["department"]) or "").strip(),
            "section": (updates.get("section", old["section"]) or "").strip() or None,
        }
        if not new_values["file_name"] or not new_values["department"]:
            raise ValueError("File name and department are required.")
        before = " | ".join(f"{k}={old.get(k) or ''}" for k in sorted(updates))
        after = " | ".join(f"{k}={new_values[k] or ''}" for k in sorted(updates))
        conn.execute(
            """
            UPDATE files
            SET file_name = ?, department = ?, section = ?,
                updated_at = ?, updated_by = ?,
                approval_status = CASE WHEN ? = 'Admin' THEN approval_status ELSE 'PENDING' END
            WHERE id = ?
            """,
            (new_values["file_name"], new_values["department"], new_values["section"],
             _utc_now(), actor["id"], actor["role"], item_id),
        )
        updated = conn.execute("SELECT * FROM files WHERE id = ?", (item_id,)).fetchone()
        _audit(conn, updated, actor, "FILE_MODIFIED", before, after)
        _notify_admins(conn, "File modified",
                       f"{old['file_id']} - {old['file_name']} was modified by {actor['name']}.")
        _broadcast(conn, "File modified",
                   f"{old['file_id']} - {new_values['file_name']} was modified.",
                   "FILE_MODIFIED")
        conn.commit()
        return True
    finally:
        conn.close()


def approve_item(item_id, admin_user_id, approved=True, remarks=""):
    conn = get_connection()
    try:
        actor = _get_user(conn, admin_user_id)
        if not _is_admin(actor):
            raise PermissionError("Only an Admin can approve or reject files.")
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND deleted_at IS NULL", (item_id,)
        ).fetchone()
        if not row:
            raise ValueError("File not found.")
        if row["approval_status"] != "PENDING":
            raise ValueError("This file is not pending approval.")
        new_status = "APPROVED" if approved else "REJECTED"
        conn.execute(
            """
            UPDATE files SET approval_status = ?, approved_by = ?, approved_at = ?,
                updated_at = ?, updated_by = ?
            WHERE id = ?
            """,
            (new_status, actor["id"], _utc_now(), _utc_now(), actor["id"], item_id),
        )
        updated = conn.execute("SELECT * FROM files WHERE id = ?", (item_id,)).fetchone()
        _audit(conn, updated, actor, f"FILE_{new_status}", "PENDING", new_status, details=remarks or None)
        creator_id = row["created_by"]
        if creator_id:
            _notify_user(conn, creator_id, f"File {new_status.lower()}",
                         f"{row['file_id']} - {row['file_name']} was {new_status.lower()}."
                         + (f" Note: {remarks}" if remarks else ""), "APPROVAL")
        _broadcast(conn, f"File {new_status.lower()}",
                   f"{row['file_id']} - {row['file_name']} was {new_status.lower()} by {actor['name']}.",
                   "APPROVAL")
        conn.commit()
        return new_status
    finally:
        conn.close()


def soft_delete_item(item_id, user_id, remarks=""):
    """Soft-delete only; no physical file/audit history is removed."""
    conn = get_connection()
    try:
        actor = _get_user(conn, user_id)
        if actor["role"] == "View Only":
            raise PermissionError("View Only users cannot remove files.")
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND deleted_at IS NULL", (item_id,)
        ).fetchone()
        if not row:
            raise ValueError("File not found.")
        old = dict(row)
        if not _is_admin(actor) and int(old.get("created_by") or -1) != actor["id"]:
            raise PermissionError("You can only remove files you created.")
        if row["status"] == "OUT":
            raise ValueError("Return the file before removing it from active records.")
        now = _utc_now()
        conn.execute(
            "UPDATE files SET deleted_at = ?, deleted_by = ?, updated_at = ?, updated_by = ? WHERE id = ?",
            (now, actor["id"], now, actor["id"], item_id),
        )
        _audit(conn, old, actor, "FILE_REMOVED", "ACTIVE", "REMOVED", details=remarks or None)
        _notify_admins(conn, "File removed",
                       f"{row['file_id']} - {row['file_name']} was removed by {actor['name']}.")
        _broadcast(conn, "File removed",
                   f"{row['file_id']} - {row['file_name']} was removed from active records.",
                   "FILE_REMOVED")
        conn.commit()
        return True
    finally:
        conn.close()


def issue_item(item_id, user_id, remarks=""):
    conn = get_connection()
    try:
        actor = _get_user(conn, user_id)
        if actor["role"] == "View Only":
            raise PermissionError("View Only users cannot retrieve files.")
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND deleted_at IS NULL", (item_id,)
        ).fetchone()
        if not row:
            raise ValueError("File not found.")
        if not _can_view_file(actor, dict(row)):
            raise PermissionError("You cannot access files outside your authorized section.")
        if row["approval_status"] != "APPROVED":
            raise ValueError("This file must be approved before it can be retrieved.")
        if row["status"] != "AVAILABLE" or row["current_holder_id"] is not None:
            raise ValueError("This file is already out.")

        conn.execute(
            "UPDATE files SET status = 'OUT', current_holder_id = ? WHERE id = ?",
            (actor["id"], item_id),
        )
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO file_movements (file_id, user_id, action, movement_time, remarks)
            VALUES (?, ?, 'ISSUED', ?, ?)
            """,
            (item_id, actor["id"], now, remarks.strip() or None),
        )
        updated = conn.execute("SELECT * FROM files WHERE id = ?", (item_id,)).fetchone()
        _audit(conn, updated, actor, "FILE_RETRIEVED", "AVAILABLE", "OUT", details=remarks or None)
        _notify_user(conn, actor["id"], "File issued successfully",
                     f"{row['file_id']} - {row['file_name']} has been issued to you.", "ISSUE")
        _broadcast(conn, "File retrieved",
                   f"{row['file_id']} - {row['file_name']} was retrieved by {actor['name']}.",
                   "ISSUE")
        conn.commit()
    finally:
        conn.close()


def return_item(item_id, user_id, remarks=""):
    conn = get_connection()
    try:
        actor = _get_user(conn, user_id)
        if actor["role"] == "View Only":
            raise PermissionError("View Only users cannot return files.")
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND deleted_at IS NULL", (item_id,)
        ).fetchone()
        if not row:
            raise ValueError("File not found.")
        if not _can_view_file(actor, dict(row)):
            raise PermissionError("You cannot access files outside your authorized section.")
        if row["status"] != "OUT" or row["current_holder_id"] is None:
            raise ValueError("This file is already available.")
        if int(row["current_holder_id"]) != actor["id"]:
            raise PermissionError("Only the current holder can return this file.")

        conn.execute(
            "UPDATE files SET status = 'AVAILABLE', current_holder_id = NULL WHERE id = ?",
            (item_id,),
        )
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO file_movements (file_id, user_id, action, movement_time, remarks)
            VALUES (?, ?, 'RETURNED', ?, ?)
            """,
            (item_id, actor["id"], now, remarks.strip() or None),
        )
        updated = conn.execute("SELECT * FROM files WHERE id = ?", (item_id,)).fetchone()
        _audit(conn, updated, actor, "FILE_RETURNED", "OUT", "AVAILABLE", details=remarks or None)
        _notify_user(conn, actor["id"], "File returned successfully",
                     f"{row['file_id']} - {row['file_name']} has been returned and is now available.",
                     "RETURN")
        _broadcast(conn, "File returned",
                   f"{row['file_id']} - {row['file_name']} was returned by {actor['name']}.",
                   "RETURN")
        conn.commit()
    finally:
        conn.close()


def get_movements(file_id=None, current_user=None):
    """Read-only movement history, filtered to files the user may view."""
    conn = get_connection()
    try:
        actor = _get_user(conn, current_user)
        query = """
            SELECT m.id, f.id AS file_row_id, f.file_id AS system_file_id,
                   f.file_name, f.department, f.section,
                   u.name AS user_name, u.staff_number, m.action,
                   m.movement_time, m.remarks
            FROM file_movements m
            JOIN files f ON m.file_id = f.id
            JOIN users u ON m.user_id = u.id
            WHERE f.deleted_at IS NULL
        """
        params = []
        if file_id is not None:
            query += " AND m.file_id = ?"
            params.append(file_id)
        query += " ORDER BY m.id DESC"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        return [r for r in rows if _can_view_file(actor, r)]
    finally:
        conn.close()


def get_audit_trail(current_user):
    """Read-only audit history. Admin sees all; users see authorized files only."""
    conn = get_connection()
    try:
        actor = _get_user(conn, current_user)
        rows = [
            dict(r) for r in conn.execute(
                "SELECT * FROM audit_trail ORDER BY id DESC"
            ).fetchall()
        ]
        if _is_admin(actor):
            return rows
        # Audit rows are immutable and only queried here; no edit/delete API exists.
        visible_file_ids = set()
        file_rows = conn.execute(
            "SELECT id, file_id, file_name, department, section FROM files"
        ).fetchall()
        for f in file_rows:
            if _can_view_file(actor, dict(f)):
                visible_file_ids.add(f["id"])
        return [
            r for r in rows
            if r["file_row_id"] in visible_file_ids
            and (r["actor_user_id"] == actor["id"] or r["file_row_id"] in visible_file_ids)
        ]
    finally:
        conn.close()


def get_notifications(user_id, include_read=True):
    conn = get_connection()
    try:
        query = """
            SELECT id, title, message, notification_type, is_read, created_at
            FROM notifications WHERE user_id = ?
        """
        params = [int(user_id)]
        if not include_read:
            query += " AND is_read = 0"
        query += " ORDER BY id DESC LIMIT 100"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def mark_notifications_read(user_id):
    conn = get_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def acknowledge_oath(user_id):
    conn = get_connection()
    try:
        actor = _get_user(conn, user_id)
        timestamp = _utc_now()
        conn.execute(
            "UPDATE users SET oath_acknowledged_at = ? WHERE id = ?",
            (timestamp, actor["id"]),
        )
        _notify_user(conn, actor["id"], "Oath acknowledged",
                     "Your Oath & Responsibilities acknowledgement has been recorded.", "OATH")
        _audit(conn, None, actor, "OATH_ACKNOWLEDGED", details="User acknowledged responsibilities")
        conn.commit()
        return timestamp
    finally:
        conn.close()
