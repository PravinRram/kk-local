import os
import sqlite3
from datetime import datetime, timedelta
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "karaoke.db")


def get_conn():
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_users_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) NOT NULL UNIQUE,
            display_name VARCHAR(120) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def create_songs_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            artist VARCHAR(200) NOT NULL,
            genre VARCHAR(50),
            duration INTEGER,
            difficulty VARCHAR(20),
            youtube_url VARCHAR(500),
            audio_url VARCHAR(500),
            lyrics_url VARCHAR(500),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def create_sessions_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(100) NOT NULL UNIQUE,
            song_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'waiting',
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        )
        """
    )


def create_session_participants_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role VARCHAR(20) DEFAULT 'singer',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def create_scores_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            mic_time INTEGER DEFAULT 0,
            accuracy REAL,
            timing REAL,
            completeness REAL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def seed_songs(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM songs")
    if cur.fetchone()[0] > 0:
        return
    songs = [
        ("Yesterday", "The Beatles", "Pop", 143, "easy", "https://www.youtube.com/watch?v=wXTJBr9tt8Q", None, "https://www.azlyrics.com/lyrics/beatles/yesterday.html"),
        ("Bohemian Rhapsody", "Queen", "Rock", 354, "hard", "https://www.youtube.com/watch?v=fJ9rUzIMcZQ", None, "https://www.azlyrics.com/lyrics/queen/bohemianrhapsody.html"),
        ("Let It Be", "The Beatles", "Pop", 243, "easy", "https://www.youtube.com/watch?v=QDYfEBY9NM4", None, "https://www.azlyrics.com/lyrics/beatles/letitbe.html"),
        ("Sweet Child O Mine", "Guns N Roses", "Rock", 356, "medium", "https://www.youtube.com/watch?v=1w7OgIMMRc4", None, "https://www.azlyrics.com/lyrics/gunsnroses/sweetchildomine.html"),
        ("Wonderful Tonight", "Eric Clapton", "Rock", 218, "easy", "https://www.youtube.com/watch?v=vUSzL2leZGE", None, "https://www.azlyrics.com/lyrics/ericclapton/wonderfultonight.html"),
        ("I Will Always Love You", "Whitney Houston", "Pop", 273, "hard", "https://www.youtube.com/watch?v=3JWTaaS7LdU", None, "https://www.azlyrics.com/lyrics/whitneyhouston/iwillalwaysloveyou.html"),
        ("Stand By Me", "Ben E. King", "Soul", 179, "easy", "https://www.youtube.com/watch?v=hwZNL7QVJjE", None, "https://www.azlyrics.com/lyrics/beneking/standbyme.html"),
        ("Hotel California", "Eagles", "Rock", 391, "medium", "https://www.youtube.com/embed/09839DpTctU?si=Jsz-j9mXT3R9Lzav", None, "https://www.azlyrics.com/lyrics/eagles/hotelcalifornia.html"),
        ("Billie Jean", "Michael Jackson", "Pop", 294, "medium", "https://www.youtube.com/watch?v=Zi_XLOBDo_Y", None, "https://www.azlyrics.com/lyrics/michaeljackson/billiejean.html"),
        ("My Way", "Frank Sinatra", "Jazz", 275, "medium", "https://www.youtube.com/watch?v=qQzdAsjWGPg", None, "https://www.azlyrics.com/lyrics/franksinatra/myway.html"),
        ("Lean On Me", "Bill Withers", "Soul", 254, "easy", "https://www.youtube.com/watch?v=fOZ-MySzAac", None, "https://www.azlyrics.com/lyrics/billwithers/leanonme.html"),
        ("Respect", "Aretha Franklin", "Soul", 147, "medium", "https://www.youtube.com/watch?v=6FOUqQt3Kg0", None, "https://www.azlyrics.com/lyrics/arethafranklin/respect.html"),
        ("Home on the Range", "Traditional", "Country", 132, "easy", "https://www.youtube.com/watch?v=MVRi9XlT4tk", None, "https://www.azlyrics.com/lyrics/traditionalsong/homeontherange.html"),
        ("Fly Me To The Moon", "Frank Sinatra", "Jazz", 147, "easy", "https://www.youtube.com/watch?v=ZEcqHA7dbwM", None, "https://www.azlyrics.com/lyrics/franksinatra/flymetothemoon.html"),
        ("You Are My Sunshine", "Traditional", "Country", 180, "easy", "https://www.youtube.com/watch?v=cGa3zFRqDn4", None, "https://www.azlyrics.com/lyrics/traditionalsong/youaremysunshine.html"),
    ]
    cur.executemany(
        """
        INSERT INTO songs (title, artist, genre, duration, difficulty, youtube_url, audio_url, lyrics_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        songs,
    )
    conn.commit()


def seed_users(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] > 0:
        return
    users = [
        ("alice", "Alice Johnson"),
        ("bob", "Bob Smith"),
        ("charlie", "Charlie Brown"),
        ("diana", "Diana Prince"),
        ("edward", "Edward Lee"),
    ]
    cur.executemany(
        "INSERT INTO users (username, display_name) VALUES (?, ?)",
        users,
    )
    conn.commit()


def seed_sessions_and_scores(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions")
    if cur.fetchone()[0] > 0:
        return
    cur.execute("SELECT id FROM songs")
    song_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT id FROM users")
    user_ids = [row[0] for row in cur.fetchall()]
    sessions_to_insert = []
    for i in range(15):
        sid = f"session_{i+1:04d}"
        song_id = random.choice(song_ids)
        status = "completed"
        started_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        completed_at = started_at + timedelta(minutes=random.randint(2, 6))
        sessions_to_insert.append(
            (sid, song_id, status, started_at.isoformat(sep=" "), completed_at.isoformat(sep=" "))
        )
    cur.executemany(
        """
        INSERT INTO sessions (session_id, song_id, status, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        sessions_to_insert,
    )
    conn.commit()
    cur.execute("SELECT id FROM sessions")
    session_ids = [row[0] for row in cur.fetchall()]
    participants_to_insert = []
    scores_to_insert = []
    for s_id in session_ids:
        user_id = random.choice(user_ids)
        participants_to_insert.append((s_id, user_id, "singer"))
        base_score = random.randint(50, 100)
        accuracy = round(random.uniform(60, 100), 2)
        timing = round(random.uniform(60, 100), 2)
        completeness = 100.0
        notes = "Great performance!" if base_score > 85 else "Keep practicing!"
        scores_to_insert.append(
            (s_id, user_id, base_score, 0, accuracy, timing, completeness, notes)
        )
    cur.executemany(
        "INSERT INTO session_participants (session_id, user_id, role) VALUES (?, ?, ?)",
        participants_to_insert,
    )
    cur.executemany(
        """
        INSERT INTO scores (session_id, user_id, score, mic_time, accuracy, timing, completeness, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        scores_to_insert,
    )
    conn.commit()


def print_summary(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM songs")
    songs_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    users_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sessions")
    sessions_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scores")
    scores_cnt = cur.fetchone()[0]
    print("Database Summary")
    print(f"  Songs: {songs_cnt}")
    print(f"  Users: {users_cnt}")
    print(f"  Sessions: {sessions_cnt}")
    print(f"  Scores: {scores_cnt}")


def init_db():
    print(f"Initializing database at {DB_PATH}")
    conn = get_conn()
    try:
        create_users_table(conn)
        create_songs_table(conn)
        create_sessions_table(conn)
        create_session_participants_table(conn)
        create_scores_table(conn)
        seed_songs(conn)
        seed_users(conn)
        seed_sessions_and_scores(conn)
        print_summary(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
