from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "parking_system.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Return a connection to the SQLite database file."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def initialize_database() -> Path:
    """Create required tables if they do not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                salt TEXT NOT NULL,
                fullname TEXT,
                phone TEXT,
                email TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                salt TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS parking_floors (floor_number INTEGER PRIMARY KEY)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_spots (
                spot_id TEXT PRIMARY KEY,
                floor_number INTEGER NOT NULL,
                spot_number TEXT NOT NULL,
                spot_type TEXT NOT NULL,
                is_available INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_tickets (
                ticket_id TEXT PRIMARY KEY,
                vehicle_number TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                color TEXT,
                owner_name TEXT NOT NULL,
                owner_mobile TEXT,
                spot_id TEXT NOT NULL,
                floor_number INTEGER NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_payments (
                payment_id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                method TEXT NOT NULL,
                status TEXT NOT NULL,
                amount REAL NOT NULL,
                paid_at TEXT
            )
            """
        )
        conn.commit()

    return DATABASE


def load_parking_state() -> dict[str, list[sqlite3.Row]]:
    """Load all persisted parking state in one read transaction."""
    with get_connection() as conn:
        return {
            "floors": conn.execute(
                "SELECT floor_number FROM parking_floors ORDER BY floor_number"
            ).fetchall(),
            "spots": conn.execute(
                "SELECT * FROM parking_spots ORDER BY floor_number, spot_id"
            ).fetchall(),
            "tickets": conn.execute(
                "SELECT * FROM parking_tickets ORDER BY entry_time"
            ).fetchall(),
            "payments": conn.execute(
                "SELECT * FROM parking_payments ORDER BY paid_at"
            ).fetchall(),
        }


def save_parking_state(
    floors: list[int],
    spots: list[dict],
    tickets: list[dict],
    payments: list[dict],
) -> None:
    """Replace the persisted parking snapshot atomically."""
    with get_connection() as conn:
        for table in ("parking_payments", "parking_tickets", "parking_spots", "parking_floors"):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            "INSERT INTO parking_floors (floor_number) VALUES (?)",
            [(floor_number,) for floor_number in floors],
        )
        conn.executemany(
            """
            INSERT INTO parking_spots
                (spot_id, floor_number, spot_number, spot_type, is_available)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (spot["spot_id"], spot["floor_number"], spot["spot_number"],
                 spot["spot_type"], int(spot["is_available"]))
                for spot in spots
            ],
        )
        conn.executemany(
            """
            INSERT INTO parking_tickets
                (ticket_id, vehicle_number, vehicle_type, color, owner_name,
                 owner_mobile, spot_id, floor_number, entry_time, exit_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (ticket["ticket_id"], ticket["vehicle_number"], ticket["vehicle_type"],
                 ticket["color"], ticket["owner_name"], ticket["owner_mobile"],
                 ticket["spot_id"], ticket["floor_number"], ticket["entry_time"],
                 ticket["exit_time"], ticket["status"])
                for ticket in tickets
            ],
        )
        conn.executemany(
            """
            INSERT INTO parking_payments
                (payment_id, ticket_id, method, status, amount, paid_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (payment["payment_id"], payment["ticket_id"], payment["method"],
                 payment["status"], payment["amount"], payment["paid_at"])
                for payment in payments
            ],
        )
        conn.commit()


def count_admins() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM admins").fetchone()
        return int(row["total"])


def count_users() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"])


def get_user_by_username(username: str) -> sqlite3.Row | None:
    normalized = username.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username)=?",
            (normalized,),
        ).fetchone()
        return row


def get_admin_by_username(username: str) -> sqlite3.Row | None:
    normalized = username.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admins WHERE LOWER(username)=?",
            (normalized,),
        ).fetchone()
        return row


def create_user_record(username: str, password: str, salt: str) -> bool:
    normalized = username.strip().lower()
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, password, salt) VALUES (?, ?, ?)",
                (normalized, password, salt),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def create_admin_record(username: str, password: str, salt: str) -> bool:
    normalized = username.strip().lower()
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO admins (username, password, salt) VALUES (?, ?, ?)",
                (normalized, password, salt),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


# Create the file and tables as soon as the module is imported.
initialize_database()

