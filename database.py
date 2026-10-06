import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "library_tracking.db"

DATA_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ---------------------------------------------------------
# PASSWORD SECURITY
# ---------------------------------------------------------

def hash_password(password):
    """
    Creates a secure password hash using PBKDF2.
    """

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000
    )

    return (
        salt.hex()
        + ":"
        + password_hash.hex()
    )


def verify_password(password, stored_hash):
    """
    Verifies a password against its stored hash.
    """

    try:
        salt_hex, hash_hex = stored_hash.split(":")

        salt = bytes.fromhex(salt_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100_000
        )

        return secrets.compare_digest(
            password_hash.hex(),
            hash_hex
        )

    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            section TEXT,
            staff_number TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'User',
            password_hash TEXT,
            oath_acknowledged INTEGER NOT NULL DEFAULT 0,
            oath_date TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # DATABASE MIGRATION
    # -----------------------------------------------------

    # If the database already existed before passwords were
    # added, add the password_hash column.
    columns = cursor.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "password_hash" not in column_names:

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN password_hash TEXT
        """)

    # -----------------------------------------------------
    # ITEMS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            section TEXT,
            barcode TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            current_holder_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (current_holder_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # MOVEMENTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS item_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            movement_time TEXT NOT NULL,
            remarks TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # NOTIFICATIONS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'INFO',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

def has_users():

    connection = get_connection()

    row = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
    """).fetchone()

    connection.close()

    return row["count"] > 0


def authenticate_user(staff_number, password):

    connection = get_connection()

    row = connection.execute("""
        SELECT
            id,
            name,
            email,
            department,
            section,
            staff_number,
            role,
            password_hash,
            oath_acknowledged,
            oath_date,
            created_at
        FROM users
        WHERE staff_number = ?
    """, (
        staff_number.strip(),
    )).fetchone()

    connection.close()

    if not row:
        return None

    if not row["password_hash"]:
        return None

    if verify_password(
        password,
        row["password_hash"]
    ):

        return dict(row)

    return None


def create_first_admin(
    name,
    email,
    department,
    section,
    staff_number,
    password
):

    connection = get_connection()

    try:

        existing = connection.execute("""
            SELECT COUNT(*) AS count
            FROM users
        """).fetchone()

        if existing["count"] > 0:
            return False, "An administrator already exists."

        connection.execute("""
            INSERT INTO users (
                name,
                email,
                department,
                section,
                staff_number,
                role,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'Admin', ?, ?)
        """, (
            name.strip(),
            email.strip().lower(),
            department.strip(),
            section.strip() if section else None,
            staff_number.strip(),
            hash_password(password),
            datetime.now().isoformat(timespec="seconds")
        ))

        connection.commit()

        return True, "Administrator account created successfully."

    except sqlite3.IntegrityError as error:

        if "email" in str(error).lower():
            return False, "That email is already registered."

        if "staff_number" in str(error).lower():
            return False, "That staff number is already registered."

        return False, "Could not create administrator."

    finally:
        connection.close()


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------

def add_user(
    name,
    email,
    department,
    section,
    staff_number,
    role,
    password
):

    connection = get_connection()

    try:

        connection.execute("""
            INSERT INTO users (
                name,
                email,
                department,
                section,
                staff_number,
                role,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name.strip(),
            email.strip().lower(),
            department.strip(),
            section.strip() if section else None,
            staff_number.strip(),
            role,
            hash_password(password),
            datetime.now().isoformat(timespec="seconds")
        ))

        connection.commit()

        return True, "User registered successfully."

    except sqlite3.IntegrityError as error:

        if "email" in str(error).lower():
            return False, "That email is already registered."

        if "staff_number" in str(error).lower():
            return False, "That staff number is already registered."

        return False, "Could not register user."

    finally:
        connection.close()


def get_users():

    connection = get_connection()

    rows = connection.execute("""
        SELECT
            id,
            name,
            email,
            department,
            section,
            staff_number,
            role,
            oath_acknowledged,
            oath_date,
            created_at
        FROM users
        ORDER BY name
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def acknowledge_oath(user_id):

    connection = get_connection()

    connection.execute("""
        UPDATE users
        SET oath_acknowledged = 1,
            oath_date = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(timespec="seconds"),
        user_id
    ))

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# ITEMS / BOOKS
# ---------------------------------------------------------

def generate_item_id():

    connection = get_connection()

    row = connection.execute("""
        SELECT id
        FROM items
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    connection.close()

    if row is None:
        number = 1
    else:
        number = row["id"] + 1

    return f"LIB-{number:06d}"


def add_item(title, department, section):

    item_id = generate_item_id()
    barcode = item_id.replace("-", "")

    connection = get_connection()

    try:

        connection.execute("""
            INSERT INTO items (
                item_id,
                title,
                department,
                section,
                barcode,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'AVAILABLE', ?)
        """, (
            item_id,
            title.strip(),
            department.strip(),
            section.strip() if section else None,
            barcode,
            datetime.now().isoformat(timespec="seconds")
        ))

        connection.commit()

        return True, {
            "item_id": item_id,
            "barcode": barcode
        }

    except sqlite3.IntegrityError:

        return False, "Could not register item."

    finally:

        connection.close()


def get_items():

    connection = get_connection()

    rows = connection.execute("""
        SELECT
            items.id,
            items.item_id,
            items.title,
            items.department,
            items.section,
            items.barcode,
            items.status,
            items.current_holder_id,
            users.name AS current_holder,
            users.email AS holder_email,
            items.created_at
        FROM items
        LEFT JOIN users
            ON items.current_holder_id = users.id
        ORDER BY items.id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def find_item(search_value):

    connection = get_connection()

    search_value = search_value.strip()

    row = connection.execute("""
        SELECT
            items.id,
            items.item_id,
            items.title,
            items.department,
            items.section,
            items.barcode,
            items.status,
            items.current_holder_id,
            users.name AS current_holder,
            users.email AS holder_email
        FROM items
        LEFT JOIN users
            ON items.current_holder_id = users.id
        WHERE
            items.item_id = ?
            OR items.barcode = ?
            OR items.title LIKE ?
        LIMIT 1
    """, (
        search_value,
        search_value,
        f"%{search_value}%"
    )).fetchone()

    connection.close()

    return dict(row) if row else None


# ---------------------------------------------------------
# ISSUE / RETURN
# ---------------------------------------------------------

def issue_item(item_id, user_id, remarks=""):

    connection = get_connection()

    item = connection.execute("""
        SELECT *
        FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:

        connection.close()

        return False, "Item not found."

    if item["status"] == "BORROWED":

        connection.close()

        return False, "This item is already borrowed."

    now = datetime.now().isoformat(timespec="seconds")

    connection.execute("""
        UPDATE items
        SET status = 'BORROWED',
            current_holder_id = ?
        WHERE id = ?
    """, (
        user_id,
        item_id
    ))

    connection.execute("""
        INSERT INTO item_movements (
            item_id,
            user_id,
            action,
            movement_time,
            remarks
        )
        VALUES (?, ?, 'ISSUED', ?, ?)
    """, (
        item_id,
        user_id,
        now,
        remarks
    ))

    connection.commit()
    connection.close()

    return True, "Item issued successfully."


def return_item(item_id, user_id, remarks=""):

    connection = get_connection()

    item = connection.execute("""
        SELECT *
        FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:

        connection.close()

        return False, "Item not found."

    if item["status"] == "AVAILABLE":

        connection.close()

        return False, "This item is already available."

    current_holder = item["current_holder_id"]

    if current_holder != user_id:

        connection.close()

        return False, "Only the current borrower can return this item."

    now = datetime.now().isoformat(timespec="seconds")

    connection.execute("""
        UPDATE items
        SET status = 'AVAILABLE',
            current_holder_id = NULL
        WHERE id = ?
    """, (item_id,))

    connection.execute("""
        INSERT INTO item_movements (
            item_id,
            user_id,
            action,
            movement_time,
            remarks
        )
        VALUES (?, ?, 'RETURNED', ?, ?)
    """, (
        item_id,
        user_id,
        now,
        remarks
    ))

    connection.commit()
    connection.close()

    return True, "Item returned successfully."


# ---------------------------------------------------------
# MOVEMENT HISTORY
# ---------------------------------------------------------

def get_movements():

    connection = get_connection()

    rows = connection.execute("""
        SELECT
            item_movements.id,
            items.item_id,
            items.title,
            items.barcode,
            users.name,
            users.email,
            users.department,
            users.section,
            users.staff_number,
            item_movements.action,
            item_movements.movement_time,
            item_movements.remarks
        FROM item_movements
        JOIN items
            ON item_movements.item_id = items.id
        JOIN users
            ON item_movements.user_id = users.id
        ORDER BY item_movements.movement_time DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ---------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------

def create_notification(
    title,
    message,
    notification_type="INFO",
    user_id=None
):

    connection = get_connection()

    connection.execute("""
        INSERT INTO notifications (
            user_id,
            title,
            message,
            notification_type,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        title,
        message,
        notification_type,
        datetime.now().isoformat(timespec="seconds")
    ))

    connection.commit()
    connection.close()


def get_notifications(user_id=None):

    connection = get_connection()

    if user_id is None:

        rows = connection.execute("""
            SELECT *
            FROM notifications
            ORDER BY created_at DESC
        """).fetchall()

    else:

        rows = connection.execute("""
            SELECT *
            FROM notifications
            WHERE user_id IS NULL
               OR user_id = ?
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()

    connection.close()

    return [dict(row) for row in rows]
