import os
import sqlite3
from urllib.parse import urlparse

from config import Config


DEFAULT_HOBBIES = [
    "Gardening",
    "Cooking",
    "Reading",
    "Music",
    "Sports",
    "Art",
    "Travel",
    "Technology",
    "Photography",
    "History",
    "Movies",
    "Gaming",
    "Crafts",
    "Yoga",
    "Walking",
    "Baking",
    "Fishing",
    "Pets",
]


def _get_sqlite_path():
    uri = Config.SQLALCHEMY_DATABASE_URI
    if not uri.startswith("sqlite:///"):
        raise ValueError("Only sqlite databases are supported by this migration helper.")
    parsed = urlparse(uri)
    path = parsed.path
    if os.name == "nt" and path.startswith("/"):
        path = path[1:]
    return path


def _connect():
    db_path = _get_sqlite_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_user_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            bio TEXT,
            location TEXT,
            phone TEXT,
            website TEXT,
            profile_picture_url TEXT,
            privacy TEXT DEFAULT 'public',
            gender TEXT,
            age_group TEXT,
            date_of_birth DATE,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hobby (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_hobbies (
            user_id INTEGER NOT NULL,
            hobby_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, hobby_id),
            FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
            FOREIGN KEY (hobby_id) REFERENCES hobby (id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS follow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            followed_id INTEGER NOT NULL,
            created_at DATETIME,
            FOREIGN KEY (follower_id) REFERENCES user (id) ON DELETE CASCADE,
            FOREIGN KEY (followed_id) REFERENCES user (id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at DATETIME,
            FOREIGN KEY (sender_id) REFERENCES user (id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES user (id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME,
            read_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_token (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            created_at DATETIME,
            expires_at DATETIME NOT NULL,
            used_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
        );
        """
    )


def seed_default_hobbies(conn):
    conn.executemany(
        "INSERT OR IGNORE INTO hobby (name) VALUES (?);",
        [(name,) for name in DEFAULT_HOBBIES],
    )


def create_indexes(conn):
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash
        ON password_reset_token (token_hash);
        """
    )


def create_all_tables():
    with _connect() as conn:
        create_user_tables(conn)
        create_indexes(conn)
        seed_default_hobbies(conn)
        conn.commit()


if __name__ == "__main__":
    create_all_tables()
