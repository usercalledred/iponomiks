import sqlite3
from contextlib import contextmanager
from pathlib import Path


# Database file location
BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "iponomiks.db"


def get_connection():
    """Create and return a database connection."""
    connection = sqlite3.connect(DATABASE_FILE)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _session():
    """Open a connection, commit on success, roll back on error, always close."""
    connection = get_connection()
    try:
        yield connection.cursor()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Create the database tables if they do not exist."""

    with _session() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trackers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                month TEXT NOT NULL,
                budget REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracker_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,

                FOREIGN KEY (tracker_id)
                    REFERENCES trackers(id)
                    ON DELETE CASCADE
            )
        """)

        # Speeds up loading a tracker's expenses.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expenses_tracker
            ON expenses(tracker_id)
        """)


def _insert_expenses(cursor, tracker_id, expenses):
    cursor.executemany("""
        INSERT INTO expenses (tracker_id, category, description, amount)
        VALUES (?, ?, ?, ?)
    """, [(tracker_id, category, description, amount)
          for category, description, amount in expenses])


def save_tracker(name, month, budget, expenses):
    """Save a new tracker and its expenses."""

    with _session() as cursor:
        cursor.execute("""
            INSERT INTO trackers (name, month, budget)
            VALUES (?, ?, ?)
        """, (name, month, budget))

        tracker_id = cursor.lastrowid
        _insert_expenses(cursor, tracker_id, expenses)

    return tracker_id


def get_all_trackers():
    """Return all saved trackers."""

    with _session() as cursor:
        cursor.execute("""
            SELECT id, name, month, budget, created_at
            FROM trackers
            ORDER BY id DESC
        """)
        return cursor.fetchall()


def get_tracker(tracker_id):
    """Return one tracker by its ID."""

    with _session() as cursor:
        cursor.execute("""
            SELECT id, name, month, budget, created_at
            FROM trackers
            WHERE id = ?
        """, (tracker_id,))
        return cursor.fetchone()


def get_tracker_expenses(tracker_id):
    """Return all expenses belonging to a tracker."""

    with _session() as cursor:
        cursor.execute("""
            SELECT category, description, amount
            FROM expenses
            WHERE tracker_id = ?
            ORDER BY id ASC
        """, (tracker_id,))
        return cursor.fetchall()


def update_tracker(tracker_id, name, month, budget, expenses):
    """Update an existing tracker and replace its expenses."""

    with _session() as cursor:
        cursor.execute("""
            UPDATE trackers
            SET name = ?, month = ?, budget = ?
            WHERE id = ?
        """, (name, month, budget, tracker_id))

        cursor.execute("DELETE FROM expenses WHERE tracker_id = ?", (tracker_id,))
        _insert_expenses(cursor, tracker_id, expenses)


def delete_tracker(tracker_id):
    """Delete a tracker and all of its expenses."""

    with _session() as cursor:
        cursor.execute("DELETE FROM expenses WHERE tracker_id = ?", (tracker_id,))
        cursor.execute("DELETE FROM trackers WHERE id = ?", (tracker_id,))