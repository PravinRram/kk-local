import sqlite3
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta


class DatabaseHelper:
    # Setup - Initializes the database helper
    def __init__(self, db_name: str = "events.db"):
        self.db_name = db_name
        self.create_events_tables()

    # Helper - Creates a database connection
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # C - Creates database tables and handles schema migrations
    def create_events_tables(self) -> None:
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                interests TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                visibility TEXT NOT NULL CHECK (visibility IN ('private','public')),
                event_type TEXT NOT NULL CHECK (event_type IN ('physical','online')),
                image_source TEXT NOT NULL CHECK (image_source IN ('upload','ai')),
                image_path TEXT,
                ai_theme TEXT,
                event_code TEXT UNIQUE,
                host_id INTEGER,
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT,
                FOREIGN KEY (host_id) REFERENCES event_users(user_id) ON DELETE SET NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_features (
                event_id INTEGER PRIMARY KEY,
                enable_group_chat INTEGER NOT NULL DEFAULT 0 CHECK (enable_group_chat IN (0,1)),
                enable_minigames INTEGER NOT NULL DEFAULT 0 CHECK (enable_minigames IN (0,1)),
                FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_participants (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES event_users(user_id) ON DELETE CASCADE,
                UNIQUE(event_id, user_id)
            )
            """
        )

        # Pre-populate users if empty
        cur.execute("SELECT count(*) FROM event_users")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO event_users (name, role, interests) VALUES ('Ethan Low', 'admin', 'tech, coding, music')")
            cur.execute("INSERT INTO event_users (name, role, interests) VALUES ('Grandma Annie', 'user', 'gardening, cooking, bingo')")

        # Migration: Check if columns exist and add if missing
        # Check users.interests
        cur.execute("PRAGMA table_info(event_users)")
        columns = [info[1] for info in cur.fetchall()]
        if "interests" not in columns:
            cur.execute("ALTER TABLE event_users ADD COLUMN interests TEXT")
            cur.execute("UPDATE event_users SET interests = 'tech, coding, music' WHERE name = 'Ethan Low'")
            cur.execute("UPDATE event_users SET interests = 'gardening, cooking, bingo' WHERE name = 'Grandma Annie'")

        # Check events.event_code
        cur.execute("PRAGMA table_info(events)")
        event_columns = [info[1] for info in cur.fetchall()]
        if "private_code" in event_columns and "event_code" not in event_columns:
            # SQLite >= 3.25 supports RENAME COLUMN
            try:
                cur.execute("ALTER TABLE events RENAME COLUMN private_code TO event_code")
            except Exception:
                # Fallback for older SQLite (not expected but good practice)
                pass
        
        # If event_code was just renamed or exists, ensure public events have codes
        if "event_code" in event_columns or "private_code" in event_columns:
             # After ensuring the event_code column exists (either via rename or fallback), update all public events with null event_code values to use the KK-{event_id} format.
             cur.execute("SELECT event_id FROM events WHERE event_code IS NULL")
             rows = cur.fetchall()
             for r in rows:
                 eid = r[0]
                 code = f"KK-{eid}"
                 cur.execute("UPDATE events SET event_code = ? WHERE event_id = ?", (code, eid))

        # Check interest_tags
        if "interest_tags" not in event_columns:
            cur.execute("ALTER TABLE events ADD COLUMN interest_tags TEXT")

        # Check event_participants.status
        cur.execute("PRAGMA table_info(event_participants)")
        part_columns = [info[1] for info in cur.fetchall()]
        if "status" not in part_columns:
            cur.execute("ALTER TABLE event_participants ADD COLUMN status TEXT DEFAULT 'going'")

        # Check events.host_id
        if "host_id" not in event_columns:
            cur.execute("ALTER TABLE events ADD COLUMN host_id INTEGER REFERENCES event_users(user_id) ON DELETE SET NULL")

        # Check events.created_by
        if "created_by" not in event_columns:
            cur.execute("ALTER TABLE events ADD COLUMN created_by INTEGER")

        conn.commit()
        conn.close()

    # D - Deletes an AI session and all associated messages and patches from the database
    def delete_ai_session(self, session_id: int) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM ai_event_patches WHERE session_id = ?", (session_id,))
        cur.execute("DELETE FROM ai_event_messages WHERE session_id = ?", (session_id,))
        cur.execute("DELETE FROM ai_event_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    # --- AI Agent Methods ---

    # C - Creates the necessary database tables for the AI Agent feature (sessions, messages, patches)
    def create_ai_agent_tables(self) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        # AI Session Table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_event_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                current_draft_json TEXT,
                linked_event_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (host_id) REFERENCES event_users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (linked_event_id) REFERENCES events(event_id) ON DELETE SET NULL
            )
            """
        )
        # AI Messages Table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_event_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'ai', 'system')),
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES ai_event_sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        # AI Patches Table (for diffs and history)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_event_patches (
                patch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                message_id INTEGER,
                patch_json TEXT,
                impact_report_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES ai_event_sessions(session_id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES ai_event_messages(message_id) ON DELETE SET NULL
            )
            """
        )
        conn.commit()
        conn.close()

    # C - Creates a new AI session for a host with an initial draft
    def create_ai_session(self, host_id: int, initial_draft: Dict[str, Any]) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_event_sessions (host_id, current_draft_json, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            (host_id, json.dumps(initial_draft)),
        )
        session_id = cur.lastrowid
        conn.commit()
        conn.close()
        return session_id

    # R - Retrieves all AI sessions belonging to a specific host, ordered by last update
    def get_user_ai_sessions(self, host_id: int) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT session_id, status, current_draft_json, updated_at
            FROM ai_event_sessions
            WHERE host_id = ?
            ORDER BY updated_at DESC
            """,
            (host_id,),
        )
        rows = cur.fetchall()
        conn.close()
        sessions = []
        for r in rows:
            sessions.append({
                "session_id": r[0],
                "status": r[1],
                "current_draft_json": r[2],
                "updated_at": r[3]
            })
        return sessions

    # R - Retrieves a specific AI session by its ID
    def get_ai_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id, host_id, status, current_draft_json, updated_at FROM ai_event_sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "session_id": row[0],
                "host_id": row[1],
                "status": row[2],
                "current_draft_json": row[3],
                "updated_at": row[4]
            }
        return None

    # C - Adds a new message to an existing AI session
    def add_ai_message(self, session_id: int, role: str, content: str) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ai_event_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        msg_id = cur.lastrowid
        conn.commit()
        conn.close()
        return msg_id

    # R - Retrieves the full message history for a specific AI session
    def get_ai_messages(self, session_id: int) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT message_id, role, content, created_at FROM ai_event_messages WHERE session_id = ? ORDER BY message_id ASC",
            (session_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [{"message_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

    # U - Updates the current draft JSON and status of an AI session
    def update_ai_session_draft(self, session_id: int, draft_json: str, status: str = "in_progress") -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE ai_event_sessions SET current_draft_json = ?, status = ?, updated_at = datetime('now') WHERE session_id = ?",
            (draft_json, status, session_id),
        )
        conn.commit()
        conn.close()

    # C - Records a patch (diff) and its impact report for version control
    def add_ai_patch(self, session_id: int, message_id: int, patch_json: str, impact_json: str) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ai_event_patches (session_id, message_id, patch_json, impact_report_json) VALUES (?, ?, ?, ?)",
            (session_id, message_id, patch_json, impact_json),
        )
        conn.commit()
        conn.close()

    # R - Retrieves all patches for a session, ordered by ID
    def get_ai_patches(self, session_id: int) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT patch_id, message_id, patch_json FROM ai_event_patches WHERE session_id = ? ORDER BY patch_id ASC",
            (session_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [{"patch_id": r[0], "message_id": r[1], "patch_json": r[2]} for r in rows]

    def get_latest_impact(self, session_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT impact_report_json FROM ai_event_patches WHERE session_id = ? ORDER BY patch_id DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
        return None

    def revert_session_to_checkpoint(self, session_id: int, checkpoint_draft: Dict[str, Any], max_message_id: int) -> None:
        """
        Reverts the session draft to a checkpoint and deletes messages/patches created after that point.
        """
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 1. Update Draft
        cur.execute(
            "UPDATE ai_event_sessions SET current_draft_json = ?, updated_at = datetime('now') WHERE session_id = ?",
            (json.dumps(checkpoint_draft), session_id),
        )
        
        # 2. Delete newer messages (Keep messages <= max_message_id)
        cur.execute(
            "DELETE FROM ai_event_messages WHERE session_id = ? AND message_id > ?",
            (session_id, max_message_id),
        )
        
        # 3. Delete newer patches (Keep patches linked to messages <= max_message_id)
        # Delete patches linked to messages after the checkpoint (using message_id relationship)
        cur.execute(
            "DELETE FROM ai_event_patches WHERE session_id = ? AND message_id > ?",
            (session_id, max_message_id),
        )
        
        conn.commit()
        conn.close()

    # R - Retrieves interest tags for a specific user
    def get_user_interests(self, user_id: int) -> str:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT interests FROM event_users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""

    # U - Updates the interest tags for a specific user
    def update_user_interests(self, user_id: int, interests_json: str) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE event_users SET interests = ? WHERE user_id = ?", (interests_json, user_id))
        conn.commit()
        conn.close()

    # R - Retrieves all users from the database
    def get_all_users(self) -> List[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, role, interests FROM event_users")
        rows = cur.fetchall()
        conn.close()
        return rows

    # R - Retrieves user details by their ID
    def get_user_by_id(self, user_id: int) -> Optional[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, role, interests FROM event_users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row

    # R - Retrieves a single event by its unique code
    def get_event_by_code(self, code: str) -> Optional[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE event_code = ?", (code,))
        row = cur.fetchone()
        conn.close()
        return row

    # R - Retrieves detailed event information including host and features
    def get_event_details_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Get event + host name + features
        query = """
            SELECT 
                e.*,
                u.name as host_name,
                ef.enable_group_chat,
                ef.enable_minigames
            FROM events e
            LEFT JOIN event_users u ON e.host_id = u.user_id
            LEFT JOIN event_features ef ON e.event_id = ef.event_id
            WHERE e.event_code = ?
        """
        cur.execute(query, (code,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            return None
            
        # Get column names
        cols = [description[0] for description in cur.description]
        event_dict = dict(zip(cols, row))
        
        conn.close()
        return event_dict

    # R - Retrieves counts of participants by status for an event
    def get_event_participant_counts(self, event_id: int) -> Dict[str, int]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT status, COUNT(*) 
            FROM event_participants 
            WHERE event_id = ? 
            GROUP BY status
        """, (event_id,))
        
        rows = cur.fetchall()
        conn.close()
        
        counts = {"going": 0, "interested": 0}
        for status, count in rows:
            if status in counts:
                counts[status] = count
                
        return counts
    
    # U - Updates the unique code for an event
    def set_event_code(self, event_id: int, code: str) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE events SET event_code = ? WHERE event_id = ?", (code, event_id))
        conn.commit()
        conn.close()

    # C - Adds a user to an event (creates or updates participant record)
    def join_event(self, event_id: int, user_id: int, status: str = "going") -> bool:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            # Check if already exists
            cur.execute("SELECT participant_id FROM event_participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
            row = cur.fetchone()
            if row:
                # Update status
                cur.execute("UPDATE event_participants SET status = ? WHERE event_id = ? AND user_id = ?", (status, event_id, user_id))
            else:
                # Insert new
                cur.execute(
                    "INSERT INTO event_participants (event_id, user_id, status) VALUES (?, ?, ?)",
                    (event_id, user_id, status)
                )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    # D - Removes a user from an event
    def leave_event(self, event_id: int, user_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM event_participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    # R - Retrieves actionable items for the host dashboard
    def get_host_action_items(self, host_id: int) -> Dict[str, List]:
        conn = self._get_conn()
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        three_days_later = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

        actions = {
            "pending_requests": [],
            "missing_posters": [],
            "ending_soon": []
        }

        # 1. Pending Requests
        # Check if 'status' column exists and has 'pending'
        try:
            cur.execute("""
                SELECT e.event_id, e.event_name, u.name, ep.joined_at, u.user_id
                FROM event_participants ep
                JOIN events e ON ep.event_id = e.event_id
                JOIN event_users u ON ep.user_id = u.user_id
                WHERE e.host_id = ? AND ep.status = 'pending'
            """, (host_id,))
            actions["pending_requests"] = [
                {"type": "pending_request", "event_id": r[0], "event_name": r[1], "user_name": r[2], "date": r[3], "user_id": r[4]}
                for r in cur.fetchall()
            ]
        except Exception:
            # Fallback for status column or value issues (schema verification occurred earlier)
            pass

        # 2. Missing Posters (Active events only)
        cur.execute("""
            SELECT event_id, event_name, start_date, event_code
            FROM events
            WHERE host_id = ? 
            AND (image_path IS NULL OR image_path = '') 
            AND end_date >= ?
        """, (host_id, today))
        actions["missing_posters"] = [
            {"type": "missing_poster", "event_id": r[0], "event_name": r[1], "start_date": r[2], "event_code": r[3]}
            for r in cur.fetchall()
        ]

        # 3. Ending Soon (Active events ending within 3 days)
        cur.execute("""
            SELECT event_id, event_name, end_date, event_code
            FROM events
            WHERE host_id = ? 
            AND end_date >= ? AND end_date <= ?
        """, (host_id, today, three_days_later))
        actions["ending_soon"] = [
            {"type": "ending_soon", "event_id": r[0], "event_name": r[1], "end_date": r[2], "event_code": r[3]}
            for r in cur.fetchall()
        ]

        conn.close()
        return actions

    # R - Retrieves the status of a specific participant
    def get_participant_status(self, event_id: int, user_id: int) -> Optional[str]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM event_participants WHERE event_id = ? AND user_id = ?",
            (event_id, user_id)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None


    # R - Checks if a user is a participant of an event
    def is_user_joined(self, event_id: int, user_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM event_participants WHERE event_id = ? AND user_id = ?",
            (event_id, user_id)
        )
        row = cur.fetchone()
        conn.close()
        return row is not None

    # C - Creates a new event record
    def insert_event(self, event_dict: Dict[str, Any]) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO events (
                event_name, start_date, end_date, start_time, end_time,
                location, description, visibility, event_type,
                image_source, image_path, ai_theme, event_code, interest_tags, host_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                event_dict.get("event_name"),
                event_dict.get("start_date"),
                event_dict.get("end_date"),
                event_dict.get("start_time"),
                event_dict.get("end_time"),
                event_dict.get("location"),
                event_dict.get("description"),
                event_dict.get("visibility"),
                event_dict.get("event_type"),
                event_dict.get("image_source"),
                event_dict.get("image_path"),
                event_dict.get("ai_theme"),
                event_dict.get("event_code"), 
                event_dict.get("interest_tags"),
                event_dict.get("host_id"),
            ),
        )
        event_id = cur.lastrowid
        conn.commit()
        conn.close()
        return event_id

    # C - Creates feature settings for an event
    def insert_event_features(self, event_id: int, features_dict: Dict[str, Any]) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO event_features (event_id, enable_group_chat, enable_minigames)
            VALUES (?, ?, ?)
            """,
            (
                event_id,
                int(features_dict.get("enable_group_chat", 0)),
                int(features_dict.get("enable_minigames", 0)),
            ),
        )
        conn.commit()
        conn.close()

    # R - Retrieves all public events
    def get_all_events(self) -> List[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.event_id, e.event_name, e.start_date, e.end_date, e.start_time, e.end_time,
                e.location, e.description, e.visibility, e.event_type,
                e.image_source, e.image_path, e.ai_theme, e.event_code,
                e.created_at, e.updated_at,
                ef.enable_group_chat, ef.enable_minigames,
                e.interest_tags,
                e.host_id
            FROM events e
            LEFT JOIN event_features ef ON e.event_id = ef.event_id
            WHERE e.visibility = 'public'
            ORDER BY e.event_id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    # R - Retrieves upcoming events for a user
    def get_user_upcoming_events(self, user_id: int) -> List[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Get today's date for filtering
        today = datetime.now().strftime("%Y-%m-%d")
        
        query = """
            SELECT DISTINCT
                e.event_id, e.event_name, e.start_date, e.end_date, e.start_time, e.end_time,
                e.location, e.description, e.visibility, e.event_type,
                e.image_source, e.image_path, e.ai_theme, e.event_code,
                e.created_at, e.updated_at,
                ef.enable_group_chat, ef.enable_minigames,
                e.interest_tags,
                e.host_id,
                CASE 
                    WHEN e.host_id = ? THEN 'host'
                    ELSE ep.status
                END as role
            FROM events e
            LEFT JOIN event_participants ep ON e.event_id = ep.event_id AND ep.user_id = ?
            LEFT JOIN event_features ef ON e.event_id = ef.event_id
            WHERE 
                (e.host_id = ? OR ep.status IN ('going', 'interested'))
                AND e.start_date >= ?
            ORDER BY e.start_date ASC
        """
        # Params: user_id (for case), user_id (for join), user_id (for host check), today
        
        cur.execute(query, (user_id, user_id, user_id, today))
        rows = cur.fetchall()
        conn.close()
        return rows

    # R - Retrieves all events associated with a user
    def get_user_events(self, user_id: int, visibility_filter: Optional[str] = None) -> List[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        query = """
            SELECT
                e.event_id, e.event_name, e.start_date, e.end_date, e.start_time, e.end_time,
                e.location, e.description, e.visibility, e.event_type,
                e.image_source, e.image_path, e.ai_theme, e.event_code,
                e.created_at, e.updated_at,
                ef.enable_group_chat, ef.enable_minigames,
                e.interest_tags,
                e.host_id,
                CASE 
                    WHEN e.host_id = ? THEN 'host'
                    ELSE ep.status
                END as status
            FROM events e
            LEFT JOIN event_participants ep ON e.event_id = ep.event_id AND ep.user_id = ?
            LEFT JOIN event_features ef ON e.event_id = ef.event_id
            WHERE (ep.user_id IS NOT NULL OR e.host_id = ?)
        """
        params = [user_id, user_id, user_id]
        
        if visibility_filter:
            query += " AND e.visibility = ?"
            params.append(visibility_filter)
            
        # Order by status (host first, then going, then others), then by event date (ascending)
        query += """
            ORDER BY 
                CASE 
                    WHEN e.host_id = ? THEN 0
                    WHEN ep.status = 'going' THEN 1 
                    ELSE 2 
                END,
                e.start_date ASC
        """
        params.append(user_id)
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows

    # D - Deletes an event and its related data
    def delete_event(self, event_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        # Delete participants first to avoid issues if CASCADE is not enabled
        cur.execute("DELETE FROM event_participants WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_features WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    # R - Retrieves an event by its ID
    def get_event_by_id(self, event_id: int) -> Optional[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
        row = cur.fetchone()
        conn.close()
        return row

    # R - Retrieves an event along with its enabled features
    def get_event_with_features(self, event_id: int) -> Optional[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.event_id, e.event_name, e.start_date, e.end_date, e.start_time, e.end_time,
                e.location, e.description, e.visibility, e.event_type,
                e.image_source, e.image_path, e.ai_theme, e.event_code,
                e.created_at, e.updated_at,
                ef.enable_group_chat, ef.enable_minigames
            FROM events e
            LEFT JOIN event_features ef ON e.event_id = ef.event_id
            WHERE e.event_id = ?
            """,
            (event_id,),
        )
        row = cur.fetchone()
        conn.close()
        return row

    # U - Updates event details and features
    def update_event(
        self,
        event_id: int,
        updated_event_dict: Dict[str, Any],
        updated_features_dict_optional: Optional[Dict[str, Any]] = None,
    ) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE events
            SET
                event_name = ?, start_date = ?, end_date = ?, start_time = ?, end_time = ?,
                location = ?, description = ?, visibility = ?, event_type = ?,
                image_source = ?, image_path = ?, ai_theme = ?, event_code = ?,
                updated_at = datetime('now')
            WHERE event_id = ?
            """,
            (
                updated_event_dict.get("event_name"),
                updated_event_dict.get("start_date"),
                updated_event_dict.get("end_date"),
                updated_event_dict.get("start_time"),
                updated_event_dict.get("end_time"),
                updated_event_dict.get("location"),
                updated_event_dict.get("description"),
                updated_event_dict.get("visibility"),
                updated_event_dict.get("event_type"),
                updated_event_dict.get("image_source"),
                updated_event_dict.get("image_path"),
                updated_event_dict.get("ai_theme"),
                updated_event_dict.get("event_code"),
                event_id,
            ),
        )
        rows_affected = cur.rowcount

        if updated_features_dict_optional is not None:
            cur.execute(
                """
                INSERT INTO event_features (event_id, enable_group_chat, enable_minigames)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    enable_group_chat = excluded.enable_group_chat,
                    enable_minigames = excluded.enable_minigames
                """,
                (
                    event_id,
                    int(updated_features_dict_optional.get("enable_group_chat", 0)),
                    int(updated_features_dict_optional.get("enable_minigames", 0)),
                ),
            )

        conn.commit()
        conn.close()
        return rows_affected > 0

    # D - Deletes an event and its related data
    def delete_event(self, event_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    # R - Retrieves pending participant requests for a host
    def get_pending_join_requests(self, host_id: int) -> List[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        query = """
            SELECT 
                ep.participant_id,
                e.event_id,
                e.event_name,
                u.user_id,
                u.name as user_name,
                ep.joined_at
            FROM event_participants ep
            JOIN events e ON ep.event_id = e.event_id
            JOIN event_users u ON ep.user_id = u.user_id
            WHERE e.host_id = ? AND ep.status = 'pending'
            ORDER BY ep.joined_at DESC
        """
        
        cur.execute(query, (host_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    # U - Updates all pending requests to 'going'
    def approve_all_pending_requests(self, host_id: int) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Update all pending requests for events hosted by this user
        query = """
            UPDATE event_participants 
            SET status = 'going' 
            WHERE status = 'pending' 
            AND event_id IN (
                SELECT event_id FROM events WHERE host_id = ?
            )
        """
        
        cur.execute(query, (host_id,))
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        return rows_affected

    # D - Deletes all pending requests
    def reject_all_pending_requests(self, host_id: int) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Delete all pending requests for events hosted by this user
        query = """
            DELETE FROM event_participants 
            WHERE status = 'pending' 
            AND event_id IN (
                SELECT event_id FROM events WHERE host_id = ?
            )
        """
        
        cur.execute(query, (host_id,))
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        return rows_affected

    # R - Retrieves statistics for the host dashboard
    def get_host_stats(self, host_id: int) -> Dict[str, int]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(*) 
            FROM event_participants ep
            JOIN events e ON ep.event_id = e.event_id
            WHERE e.host_id = ? AND ep.status = 'going'
        """, (host_id,))
        total_participants = cur.fetchone()[0]
        
        # 2. Upcoming Events count (this week)
        today = datetime.now().date()
        week_later = today + timedelta(days=7)
        
        cur.execute("""
            SELECT COUNT(*) 
            FROM events 
            WHERE host_id = ? 
            AND start_date >= ? AND start_date <= ?
        """, (host_id, today.strftime("%Y-%m-%d"), week_later.strftime("%Y-%m-%d")))
        upcoming_count = cur.fetchone()[0]
        
        conn.close()
        return {
            "total_participants": total_participants,
            "upcoming_this_week": upcoming_count
        }

    def get_signups_over_time(self, host_id: int, days: int = 30) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        start_date_obj = datetime.now().date() - timedelta(days=days - 1)
        start_date_str = start_date_obj.strftime("%Y-%m-%d")
        cur.execute(
            """
            SELECT substr(ep.joined_at, 1, 10) as join_date, COUNT(*)
            FROM event_participants ep
            JOIN events e ON ep.event_id = e.event_id
            WHERE e.host_id = ? AND ep.status = 'going' AND substr(ep.joined_at, 1, 10) >= ?
            GROUP BY join_date
            ORDER BY join_date
            """,
            (host_id, start_date_str),
        )
        rows = cur.fetchall()
        conn.close()
        counts_map = {r[0]: r[1] for r in rows}
        result: List[Dict[str, Any]] = []
        current = start_date_obj
        today = datetime.now().date()
        while current <= today:
            key = current.strftime("%Y-%m-%d")
            result.append({"date": key, "count": counts_map.get(key, 0)})
            current += timedelta(days=1)
        return result

    def get_events_type_visibility_breakdown(self, host_id: int) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            """
            SELECT event_type, visibility, COUNT(*)
            FROM events
            WHERE host_id = ? AND start_date >= ?
            GROUP BY event_type, visibility
            """,
            (host_id, today),
        )
        rows = cur.fetchall()
        conn.close()
        data: List[Dict[str, Any]] = []
        for event_type, visibility, count in rows:
            label = f"{event_type.capitalize()} {visibility.capitalize()}"
            data.append({"label": label, "count": count})
        return data

    # R - Retrieves event suggestions for the host
    def get_smart_suggestions(self, host_id: int) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Find upcoming events with low signups (< 5)
        # Assumes a default capacity of 20 for display purposes
        query = """
            SELECT 
                e.event_id, 
                e.event_name, 
                e.event_code,
                COUNT(ep.participant_id) as current_signups
            FROM events e
            LEFT JOIN event_participants ep ON e.event_id = ep.event_id AND ep.status = 'going'
            WHERE e.host_id = ? AND e.start_date >= ?
            GROUP BY e.event_id
            HAVING current_signups < 5
        """
        
        cur.execute(query, (host_id, today))
        rows = cur.fetchall()
        conn.close()
        
        suggestions = []
        for r in rows:
            suggestions.append({
                "event_id": r[0],
                "event_name": r[1],
                "event_code": r[2],
                "signups": r[3],
                "capacity": 20 # Hardcoded for now as per requirement visualization
            })
            
        return suggestions

    # R - Retrieves recent activity logs for the host
    def get_recent_activity(self, host_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Get recent joins for user's events
        query = """
            SELECT 
                u.name as user_name,
                e.event_name,
                ep.joined_at,
                ep.status
            FROM event_participants ep
            JOIN events e ON ep.event_id = e.event_id
            JOIN event_users u ON ep.user_id = u.user_id
            WHERE e.host_id = ?
            ORDER BY ep.joined_at DESC
            LIMIT ?
        """
        
        cur.execute(query, (host_id, limit))
        rows = cur.fetchall()
        conn.close()
        
        activities = []
        for r in rows:
            # Pass raw timestamp; formatting handled by frontend or helper logic
            activities.append({
                "user_name": r[0],
                "event_name": r[1],
                "joined_at": r[2],
                "status": r[3]
            })
            
        return activities

    # U - Updates the status of a specific participant
    def update_participant_status(self, participant_id: int, status: str) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE event_participants SET status = ? WHERE participant_id = ?", (status, participant_id))
        conn.commit()
        conn.close()

    # R - Retrieves participant details by ID
    def get_participant_by_id(self, participant_id: int) -> Optional[Tuple]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM event_participants WHERE participant_id = ?", (participant_id,))
        row = cur.fetchone()
        conn.close()
        return row

    # D - Deletes a participant record
    def delete_participant(self, participant_id: int) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM event_participants WHERE participant_id = ?", (participant_id,))
        conn.commit()
        conn.close()

