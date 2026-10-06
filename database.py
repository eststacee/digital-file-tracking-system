import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "filing_system.db"

DATA_DIR.mkdir(exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            staff_number TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_number TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            department TEXT NOT NULL,
            barcode TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            current_holder_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (current_holder_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            movement_time TEXT NOT NULL,
            remarks TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def add_user(name, email, department, staff_number):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (
                name, email, department, staff_number, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            email,
            department,
            staff_number,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

        conn.commit()
        return True, "User registered successfully."

    except sqlite3.IntegrityError:
        return False, "Email or staff number already exists."

    finally:
        conn.close()


def get_users():
    conn = get_connection()

    users = conn.execute("""
        SELECT *
        FROM users
        ORDER BY name
    """).fetchall()

    conn.close()
    return users


def add_file(file_number, file_name, department, barcode):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO files (
                file_number,
                file_name,
                department,
                barcode,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'AVAILABLE', ?)
        """, (
            file_number,
            file_name,
            department,
            barcode,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

        conn.commit()
        return True, "File registered successfully."

    except sqlite3.IntegrityError:
        return False, "File number or barcode already exists."

    finally:
        conn.close()


def get_files():
    conn = get_connection()

    files = conn.execute("""
        SELECT
            f.*,
            u.name AS current_holder,
            u.email AS holder_email
        FROM files f
        LEFT JOIN users u
            ON f.current_holder_id = u.id
        ORDER BY f.file_number
    """).fetchall()

    conn.close()
    return files


def find_file(search_value):
    conn = get_connection()

    file = conn.execute("""
        SELECT
            f.*,
            u.name AS current_holder,
            u.email AS holder_email
        FROM files f
        LEFT JOIN users u
            ON f.current_holder_id = u.id
        WHERE
            f.file_number = ?
            OR f.barcode = ?
            OR LOWER(f.file_name) LIKE LOWER(?)
        LIMIT 1
    """, (
        search_value,
        search_value,
        f"%{search_value}%",
    )).fetchone()

    conn.close()
    return file


def pick_file(file_id, user_id, remarks=""):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        file = cursor.execute("""
            SELECT *
            FROM files
            WHERE id = ?
        """, (file_id,)).fetchone()

        if not file:
            return False, "File not found."

        if file["status"] == "OUT":
            return False, "This file is already out."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE files
            SET status = 'OUT',
                current_holder_id = ?
            WHERE id = ?
        """, (user_id, file_id))

        cursor.execute("""
            INSERT INTO file_movements (
                file_id,
                user_id,
                action,
                movement_time,
                remarks
            )
            VALUES (?, ?, 'PICKED', ?, ?)
        """, (file_id, user_id, now, remarks))

        conn.commit()
        return True, "File successfully picked."

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"

    finally:
        conn.close()


def return_file(file_id, user_id, remarks=""):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        file = cursor.execute("""
            SELECT *
            FROM files
            WHERE id = ?
        """, (file_id,)).fetchone()

        if not file:
            return False, "File not found."

        if file["status"] == "AVAILABLE":
            return False, "This file is already available."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE files
            SET status = 'AVAILABLE',
                current_holder_id = NULL
            WHERE id = ?
        """, (file_id,))

        cursor.execute("""
            INSERT INTO file_movements (
                file_id,
                user_id,
                action,
                movement_time,
                remarks
            )
            VALUES (?, ?, 'RETURNED', ?, ?)
        """, (file_id, user_id, now, remarks))

        conn.commit()
        return True, "File successfully returned."

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"

    finally:
        conn.close()


def get_movements():
    conn = get_connection()

    movements = conn.execute("""
        SELECT
            m.id,
            f.file_number,
            f.file_name,
            f.barcode,
            u.name,
            u.email,
            u.department,
            u.staff_number,
            m.action,
            m.movement_time,
            m.remarks
        FROM file_movements m
        INNER JOIN files f
            ON m.file_id = f.id
        INNER JOIN users u
            ON m.user_id = u.id
        ORDER BY m.movement_time DESC
    """).fetchall()

    conn.close()
    return movements
