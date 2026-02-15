import json
import threading
import uuid
from datetime import datetime

from flask import jsonify, render_template, request, session, g

from database import (
    add_participant_to_session,
    create_session,
    get_leaderboard,
    get_or_create_user,
    save_score,
    get_monthly_top_players,
    get_user_ranking,
    get_user_active_sessions
)

from models import Session as SessionModel
from models import SessionParticipant, Song, User, db

session_clients = {}  # Map of session_id to list of websocket clients
session_locks = {}  # Map of session_id to threading.Lock for thread safety
sessions_lock = (
    threading.Lock()
)  # Lock for managing session_clients and session_locks dictionaries


# main page (/karaoke)
def index():
    top_players = get_monthly_top_players(3)
    return render_template("karaoke/home.html", top_players=top_players)

# create a new karaoke session page
def create_session_page():
    return render_template("karaoke/create.html")


# API Functions for song management
def get_songs():
    """Get all songs with optional filtering"""
    genre = request.args.get("genre")
    difficulty = request.args.get("difficulty")
    search = request.args.get("search")

    query = Song.query

    if genre:
        query = query.filter_by(genre=genre)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if search:
        query = query.filter(
            (Song.title.ilike(f"%{search}%")) | (Song.artist.ilike(f"%{search}%"))
        )

    songs = query.all()
    return jsonify([song.to_dict() for song in songs])


def get_song(song_id):
    """Get a single song by ID"""
    song = Song.query.get(song_id)
    if not song:
        return jsonify({"error": "Song not found"}), 404
    return jsonify(song.to_dict())


def search_songs_external(query):
    """Search for songs using external API (iTunes)"""
    from api_integrations import search_songs_itunes, SongSearchAPIError

    if not query or len(query.strip()) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400

    try:
        results = search_songs_itunes(query.strip(), limit=20)
        return jsonify({
            "results": results,
            "count": len(results),
            "query": query.strip()
        })
    except SongSearchAPIError as e:
        return jsonify({"error": str(e)}), 500


def get_song_lyrics(song_id):
    """Get lyrics for a song by ID"""
    from api_integrations import fetch_lyrics_from_lrclib, LyricsAPIError

    song = Song.query.get(song_id)
    if not song:
        return jsonify({"error": "Song not found"}), 404

    try:
        # Try to fetch lyrics from LRCLIB API
        lyrics_data = fetch_lyrics_from_lrclib(
            title=song.title,
            artist=song.artist,
            duration=song.duration
        )

        if lyrics_data and lyrics_data.get('lyrics'):
            # Return synced lyrics in LRC format
            return jsonify({
                "lyrics": lyrics_data['lyrics'],
                "instrumental": lyrics_data.get('instrumental', False),
                "source": "lrclib"
            })
        else:
            # No lyrics found, return fallback
            lyrics = generate_sample_lyrics(song.title, song.artist)
            return jsonify({
                "lyrics": lyrics,
                "source": "fallback"
            })

    except LyricsAPIError as e:
        print(f"Lyrics API error: {e}")
        # Fallback to generated lyrics on API error
        lyrics = generate_sample_lyrics(song.title, song.artist)
        return jsonify({
            "lyrics": lyrics,
            "source": "fallback",
            "note": "API temporarily unavailable"
        })


def generate_sample_lyrics(title, artist):
    """Generate sample LRC format lyrics for demo purposes"""
    # For demo purposes, we'll create a simple LRC file with timestamps
    lyrics_lines = []

    # Header info
    lyrics_lines.append(f"[ti:{title}]")
    lyrics_lines.append(f"[ar:{artist}]")
    lyrics_lines.append(f"[length:03:30]")
    lyrics_lines.append("")

    # Common lyrics templates based on song name
    if "Yesterday" in title or "yesterday" in title.lower():
        lyrics_lines.extend(
            [
                "[00:00.00]",
                "[00:05.00]Yesterday, all my troubles seemed so far away",
                "[00:10.00]Now it looks as though they're here to stay",
                "[00:15.00]Oh, I believe in yesterday",
                "[00:20.00]",
                "[00:25.00]Suddenly, I'm not half the man I used to be",
                "[00:30.00]There's a shadow hanging over me",
                "[00:35.00]Oh, yesterday came suddenly",
            ]
        )
    elif "Let It Be" in title or "let it be" in title.lower():
        lyrics_lines.extend(
            [
                "[00:00.00]",
                "[00:05.00]When I find myself in times of trouble",
                "[00:10.00]Mother Mary comes to me",
                "[00:15.00]Speaking words of wisdom, let it be",
                "[00:20.00]",
                "[00:25.00]And in my hour of darkness",
                "[00:30.00]She is standing right in front of me",
                "[00:35.00]Speaking words of wisdom, let it be",
            ]
        )
    elif "Bohemian Rhapsody" in title or "bohemian rhapsody" in title.lower():
        lyrics_lines.extend(
            [
                "[00:00.00]",
                "[00:05.00]Is this the real life? Is this just fantasy?",
                "[00:10.00]Caught in a landslide, no escape from reality",
                "[00:15.00]Open your eyes, look up to the skies and see",
                "[00:20.00]I'm just a poor boy, I need no sympathy",
                "[00:25.00]Because I'm easy come, easy go, little high, little low",
                "[00:30.00]Any way the wind blows doesn't really matter to me, to me",
            ]
        )
    else:
        # Generic lyrics for other songs
        lyrics_lines.extend(
            [
                "[00:00.00]",
                f"[00:05.00]This is {title}",
                f"[00:10.00]By {artist}",
                "[00:15.00]Thank you for singing with KampongKonek",
                "[00:20.00]Connect across generations through music",
                "[00:25.00]Sing your heart out!",
                "[00:30.00]And enjoy the karaoke experience",
            ]
        )

    return "\n".join(lyrics_lines)


def create_song(data):
    """Create a new song with validation"""
    # Validate required fields
    required_fields = [
        "title",
        "artist",
        "genre",
        "difficulty",
        "duration",
        "youtube_url",
    ]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

    # Validate title  length
    if len(data["title"]) < 2 or len(data["title"]) > 200:
        return jsonify({"error": "Title must be between 2 and 200 characters"}), 400

    # Validate artist length
    if len(data["artist"]) < 2 or len(data["artist"]) > 200:
        return jsonify(
            {"error": "Artist name must be between 2 and 200 characters"}
        ), 400

    # Validate difficulty
    valid_difficulties = ["easy", "medium", "hard"]
    if data["difficulty"] not in valid_difficulties:
        return jsonify(
            {"error": f"Difficulty must be one of: {', '.join(valid_difficulties)}"}
        ), 400

    # Validate duration
    try:
        duration = int(data["duration"])
        if duration < 30 or duration > 900:
            return jsonify(
                {"error": "Duration must be between 30 and 900 seconds"}
            ), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Duration must be a valid number"}), 400

    # Validate YouTube URL
    youtube_url = data["youtube_url"]
    if not (
        youtube_url.startswith("https://www.youtube.com/")
        or youtube_url.startswith("https://youtu.be/")
        or youtube_url.startswith("http://www.youtube.com/")
        or youtube_url.startswith("http://youtu.be/")
    ):
        return jsonify(
            {
                "error": "Invalid YouTube URL. Must start with https://www.youtube.com/ or https://youtu.be/"
            }
        ), 400

    # Create song
    song = Song(
        title=data["title"].strip(),
        artist=data["artist"].strip(),
        genre=data["genre"],
        difficulty=data["difficulty"],
        duration=duration,
        youtube_url=youtube_url.strip(),
        lyrics_url=data.get("lyrics_url", "").strip() or None,
    )

    db.session.add(song)
    db.session.commit()

    return jsonify(song.to_dict()), 201


def update_song(song_id, data):
    """Update an existing song with validation"""
    song = Song.query.get(song_id)
    if not song:
        return jsonify({"error": "Song not found"}), 404

    # Validate and update fields if provided
    if "title" in data:
        title = data["title"].strip()
        if len(title) < 2 or len(title) > 200:
            return jsonify({"error": "Title must be between 2 and 200 characters"}), 400
        song.title = title

    if "artist" in data:
        artist = data["artist"].strip()
        if len(artist) < 2 or len(artist) > 200:
            return jsonify(
                {"error": "Artist name must be between 2 and 200 characters"}
            ), 400
        song.artist = artist

    if "genre" in data:
        song.genre = data["genre"]

    if "difficulty" in data:
        valid_difficulties = ["easy", "medium", "hard"]
        if data["difficulty"] not in valid_difficulties:
            return jsonify(
                {"error": f"Difficulty must be one of: {', '.join(valid_difficulties)}"}
            ), 400
        song.difficulty = data["difficulty"]

    if "duration" in data:
        try:
            duration = int(data["duration"])
            if duration < 30 or duration > 900:
                return jsonify(
                    {"error": "Duration must be between 30 and 900 seconds"}
                ), 400
            song.duration = duration
        except (ValueError, TypeError):
            return jsonify({"error": "Duration must be a valid number"}), 400

    if "youtube_url" in data:
        youtube_url = data["youtube_url"].strip()
        if not (
            youtube_url.startswith("https://www.youtube.com/")
            or youtube_url.startswith("https://youtu.be/")
            or youtube_url.startswith("http://www.youtube.com/")
            or youtube_url.startswith("http://youtu.be/")
        ):
            return jsonify({"error": "Invalid YouTube URL"}), 400
        song.youtube_url = youtube_url

    if "lyrics_url" in data:
        song.lyrics_url = data["lyrics_url"].strip() or None

    db.session.commit()

    return jsonify(song.to_dict()), 200


def delete_song(song_id):
    """Delete a song (only if not used in active sessions)"""
    song = Song.query.get(song_id)
    if not song:
        return jsonify({"error": "Song not found"}), 404

    # Check if song is used in any active or waiting sessions
    active_sessions = (
        SessionModel.query.filter_by(song_id=song_id)
        .filter(SessionModel.status.in_(["waiting", "active"]))
        .count()
    )

    if active_sessions > 0:
        return jsonify(
            {"error": "Cannot delete song with active or waiting sessions"}
        ), 400

    db.session.delete(song)
    db.session.commit()

    return jsonify({"message": "Song deleted successfully"}), 200


# API Functions for session management
def create_karaoke_session(data):
    """Create a new karaoke session"""
    song_id = data.get("song_id")
    username = session.get("username") or data.get("username", "guest")
    display_name = data.get("display_name", username)
    if g.current_user:
        username = g.current_user.username
        display_name = g.current_user.display_name or g.current_user.username
    replace_existing = data.get("replace_existing", False)

    if not song_id:
        return jsonify({"error": "song_id is required"}), 400

    song = Song.query.get(song_id)
    if not song:
        return jsonify({"error": "Song not found"}), 404

    # Create or get user
    user = get_or_create_user(username, display_name)

    # Check if user already has a waiting or active session
    existing_session = (
        SessionModel.query.join(SessionParticipant)
        .filter(
            SessionParticipant.user_id == user.id,
            SessionModel.status.in_(["waiting", "active"]),
        )
        .first()
    )

    if existing_session:
        # If replace_existing is True, delete the old session and create a new one
        if replace_existing:
            # Delete the existing session
            db.session.delete(existing_session)
            db.session.commit()
        else:
            # Return info about existing session for user confirmation
            return jsonify(
                {
                    "error": "You already have a song in the queue",
                    "session_id": existing_session.session_id,
                    "song": existing_session.song.to_dict(),
                    "status": existing_session.status,
                }
            ), 409

    # Create session
    session_id = str(uuid.uuid4())
    karaoke_session = create_session(session_id, song_id)

    # Add user as participant
    add_participant_to_session(session_id, user.id, role="singer")

    return jsonify(
        {"session_id": session_id, "song": song.to_dict(), "user": user.to_dict()}
    ), 201


def get_session_info(session_id):
    """Get information about a session"""
    session = SessionModel.query.filter_by(session_id=session_id).first()
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.to_dict())


# API Functions for score management
def submit_score(data):
    """Submit a score for a session"""
    session_id = data.get("session_id")
    username = data.get("username")
    display_name = data.get("display_name")
    score = data.get("score")
    mic_time = data.get("mic_time", 0)  # Time in seconds with mic on
    accuracy = data.get("accuracy")
    timing = data.get("timing")
    completeness = data.get("completeness")
    notes = data.get("notes")

    if g.current_user:
        username = g.current_user.username
        display_name = g.current_user.display_name or g.current_user.username

    if not all([session_id, username, score is not None]):
        return jsonify({"error": "session_id, username, and score are required"}), 400

    # Get or create user
    user = get_or_create_user(username, display_name)

    # Update display name if provided
    if display_name and user.display_name != display_name:
        user.display_name = display_name
        db.session.commit()

    # Save score
    score_entry = save_score(
        session_id=session_id,
        user_id=user.id,
        score=score,
        mic_time=mic_time,
        accuracy=accuracy,
        timing=timing,
        completeness=completeness,
        notes=notes,
    )

    if not score_entry:
        return jsonify({"error": "Session not found"}), 404

    # Update session status to completed
    session = SessionModel.query.filter_by(session_id=session_id).first()
    if session:
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.session.commit()

    return jsonify(score_entry.to_dict()), 201


def get_leaderboard_data(limit=10):
    """Get leaderboard data - sorted by total karaoke time"""
    leaderboard_data = get_leaderboard(limit)
    # Format for frontend
    formatted_data = []
    for entry in leaderboard_data:
        formatted_data.append({
            'user': entry['user'].to_dict(),
            'total_mic_time': entry['total_mic_time'],
            'session_count': entry['session_count'],
            'created_at': entry['created_at'].isoformat()
        })
    return jsonify(formatted_data)


def get_song_queue():
    """Get queue of songs for the current user"""
    user = g.current_user
    if not user:
        return jsonify([])

    # Get user's waiting or active sessions
    sessions = (
        SessionModel.query.join(SessionParticipant)
        .filter(
            SessionParticipant.user_id == user.id,
            SessionModel.status.in_(["waiting", "active"]),
        )
        .order_by(SessionModel.created_at.desc())
        .all()
    )

    queue_data = []
    for session in sessions:
        queue_data.append(
            {
                "session_id": session.session_id,
                "song_id": session.song.id,
                "title": session.song.title,
                "artist": session.song.artist,
                "genre": session.song.genre,
                "difficulty": session.song.difficulty,
                "duration": session.song.duration,
                "queued_at": session.created_at.isoformat(),
            }
        )

    return jsonify(queue_data)


def delete_queue_item(session_id):
    """Delete a song from the user's queue"""
    user = g.current_user
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get session
    session = SessionModel.query.filter_by(session_id=session_id).first()
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Check if user is a participant
    participant = SessionParticipant.query.filter_by(
        session_id=session.id, user_id=user.id
    ).first()

    if not participant:
        return jsonify({"error": "You are not a participant in this session"}), 403

    # Only allow deletion if session is waiting or active (not completed)
    if session.status == "completed":
        return jsonify({"error": "Cannot delete a completed session"}), 400

    # Delete the session
    db.session.delete(session)
    db.session.commit()

    return jsonify({"message": "Session deleted successfully"}), 200


def get_user_ranking_data():
    """Get current user's ranking and stats"""
    user = g.current_user
    if not user:
        return jsonify({
            "ranking": None,
            "total_mic_time": 0,
            "total_sessions": 0,
            "avg_score": 0,
            "highest_score": 0
        })

    ranking_data = get_user_ranking(user.id)
    return jsonify(ranking_data)


def get_user_sessions():
    """Get current user's active sessions"""
    user = g.current_user
    if not user:
        return jsonify([])

    sessions = get_user_active_sessions(user.id)

    # Format sessions for frontend
    sessions_data = []
    for session in sessions:
        sessions_data.append({
            "session_id": session.session_id,
            "status": session.status,
            "song": session.song.to_dict(),
            "created_at": session.created_at.isoformat()
        })

    return jsonify(sessions_data)


def audio_ws(ws, session_id):
    """
    Handle WebSocket connection for a specific karaoke session.
    Routes audio between all clients in the same session (supports multiple participants).
    """
    client_index = None
    user_id_for_client = None  # Track user ID for this connection

    # Initialize session data structures if needed
    with sessions_lock:
        if session_id not in session_clients:
            session_clients[session_id] = []
            session_locks[session_id] = threading.Lock()

    # Get the session lock
    session_lock = session_locks[session_id]

    with session_lock:
        # Add client to session (no limit on number of participants)
        session_clients[session_id].append(ws)
        client_index = len(session_clients[session_id]) - 1
        print(f"[Session {session_id}] Client {client_index} connected (Total: {len(session_clients[session_id])})")

        # Notify client they're connected
        try:
            ws.send(f"connected:{client_index}")
        except Exception as e:
            print(f"Error notifying client of connection: {e}")

        # Notify all existing clients that a new participant joined
        participant_count = len(session_clients[session_id])
        for i, client in enumerate(session_clients[session_id]):
            try:
                client.send(json.dumps({
                    "type": "PARTICIPANT_UPDATE",
                    "count": participant_count,
                    "client_index": i
                }))
            except Exception as e:
                print(f"[Session {session_id}] Error notifying client {i} of participant update: {e}")

        # Update session status to active when first participant joins
        if participant_count == 1:
            try:
                session = SessionModel.query.filter_by(session_id=session_id).first()
                if session and session.status == "waiting":
                    session.status = "active"
                    session.started_at = datetime.utcnow()
                    db.session.commit()
                    print(f"[Session {session_id}] Status updated to active")
            except Exception as e:
                print(f"Error updating session status: {e}")

    try:
        while True:
            data = ws.receive()
            if data is None:
                print(f"[Session {session_id}] Client {client_index} disconnected")
                break

            # Handle binary audio data
            if isinstance(data, (bytes, bytearray)):
                with session_lock:
                    # Broadcast audio to all other participants in the same session
                    for other in session_clients[session_id]:
                        if other is not ws:
                            try:
                                other.send(data)
                            except Exception as e:
                                print(
                                    f"[Session {session_id}] Error broadcasting audio to participant: {e}"
                                )

            # Handle text messages (control messages)
            else:
                print(f"[Session {session_id}] Client {client_index} sent text: {data}")
                # Try to parse as JSON for control messages (PLAY, PAUSE, USER_JOIN)
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type")

                    if msg_type == "USER_JOIN":
                        # Handle user joining - add them as a participant
                        user_id = msg.get("user_id")
                        display_name = msg.get("display_name", "Guest")

                        if user_id:
                            user_id_for_client = user_id
                            # Get or create user
                            user = get_or_create_user(user_id, display_name)

                            # Check if user is already a participant in this session
                            session = SessionModel.query.filter_by(session_id=session_id).first()
                            if session:
                                existing_participant = SessionParticipant.query.filter_by(
                                    session_id=session.id,
                                    user_id=user.id
                                ).first()

                                if not existing_participant:
                                    # Add user as participant
                                    add_participant_to_session(session_id, user.id, role="singer")
                                    print(f"[Session {session_id}] Added user {user_id} as participant")
                                else:
                                    print(f"[Session {session_id}] User {user_id} already a participant")

                    elif msg_type in ["PLAY", "PAUSE"]:
                        # Relay control message to all other clients
                        with session_lock:
                            for other in session_clients[session_id]:
                                if other is not ws:
                                    try:
                                        other.send(data)
                                        print(
                                            f"[Session {session_id}] Relayed {msg_type} to other participants"
                                        )
                                    except Exception as e:
                                        print(
                                            f"[Session {session_id}] Error relaying control message: {e}"
                                        )
                except (json.JSONDecodeError, ValueError):
                    # Not a JSON message, ignore
                    pass

    finally:
        # Remove client from session
        with session_lock:
            if ws in session_clients[session_id]:
                session_clients[session_id].remove(ws)
                remaining_count = len(session_clients[session_id])
                print(
                    f"[Session {session_id}] Client {client_index} removed from session (Remaining: {remaining_count})"
                )

                # Notify all remaining clients about the updated participant count
                if remaining_count > 0:
                    for i, client in enumerate(session_clients[session_id]):
                        try:
                            client.send(json.dumps({
                                "type": "PARTICIPANT_UPDATE",
                                "count": remaining_count,
                                "client_index": i
                            }))
                        except Exception as e:
                            print(
                                f"[Session {session_id}] Error notifying client {i} of disconnection: {e}"
                            )

                # Clean up empty sessions and mark as completed in database
                if remaining_count == 0:
                    # Update session status to completed in database
                    session = SessionModel.query.filter_by(session_id=session_id).first()
                    if session and session.status != "completed":
                        session.status = "completed"
                        session.completed_at = datetime.utcnow()
                        db.session.commit()
                        print(f"[Session {session_id}] Session marked as completed in database")

                    with sessions_lock:
                        del session_clients[session_id]
                        del session_locks[session_id]
                    print(f"[Session {session_id}] Session cleaned up")
