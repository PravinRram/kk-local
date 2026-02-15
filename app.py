import base64
import json
import os
import secrets
import uuid
from datetime import datetime
from urllib.parse import urlencode

import dotenv

dotenv.load_dotenv()

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_bootstrap import Bootstrap5
from flask_sock import Sock
from flask_socketio import SocketIO, emit, join_room, leave_room
from markupsafe import Markup
from werkzeug.utils import secure_filename
from sqlalchemy import or_

# Import unified config and models
from config import config, Config
from models import (
    db, User, Forum, Post, Comment, Like, Notification,
    Report, Ban, DeletedPost, Hobby, Message, PasswordResetToken,
    Follow, Session as SessionModel, Score
)
from extensions import socketio
from routes.event_routes import event_bp
from karaoke import (
    audio_ws,
    create_karaoke_session,
    create_session_page,
    create_song,
    delete_queue_item,
    delete_song,
    get_leaderboard_data,
    get_session_info,
    get_song,
    get_song_lyrics,
    get_song_queue,
    get_songs,
    get_user_ranking_data,
    get_user_sessions,
    search_songs_external,
    submit_score,
    update_song,
    index as karaoke_index
)
from database import seed_default_songs
from decorators import login_required

# Initialize extensions globally for decorators
sock = Sock()
bootstrap = Bootstrap5()

def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app)
    sock.init_app(app)
    bootstrap.init_app(app)

    # Ensure upload folder exists
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
         upload_folder = os.path.join(app.root_path, "instance", "uploads")
         app.config["UPLOAD_FOLDER"] = upload_folder
    
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    with app.app_context():
        db.create_all()
        # Initialize Hobbies if empty (from Account logic)
        if not Hobby.query.first():
            for name in app.config['INTERESTS']:
                if not Hobby.query.filter_by(name=name).first():
                    db.session.add(Hobby(name=name))
            db.session.commit()
        seed_default_songs()

    # --- Helpers & Decorators (Merged) ---

    @app.before_request
    def load_current_user():
        user_id = session.get("user_id")
        g.current_user = User.query.get(user_id) if user_id else None
        g.user = g.current_user
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.context_processor
    def inject_user():
        notification_count = 0
        joined_forums = []
        suggested_forums = []
        
        if g.current_user:
            # Account Notification Count
            notification_count = Notification.query.filter_by(
                user_id=g.current_user.id, read_at=None
            ).count()
            
            # Forum Data for Sidebar
            # Handle case where joined_forums might be a property or relationship
            joined_forums = getattr(g.current_user, 'joined_forums', [])
            
            # Get user interests and exclude joined forums
            from services import ForumService
            user_interests = [h.name for h in g.current_user.hobbies]
            forum_service = ForumService(db.session)
            suggested_forums = forum_service.get_recommended_forums(g.current_user.id, user_interests)
            # Limit to 5 for the carousel
            suggested_forums = suggested_forums[:5]

        def avatar_url(path):
            if not path or not path.strip():
                return url_for("static", filename="img/default_avatar.png")
            if path.startswith("uploads/"):
                filename = path.split("/", 1)[1] if "/" in path else path
                return url_for("auth.uploaded_file", filename=filename)
            return url_for("static", filename=path)

        def csrf_token():
            token = session.get("csrf_token", "")
            return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')

        return {
            "current_user": g.current_user,
            "notification_count": notification_count,
            "avatar_url": avatar_url,
            "csrf_token": csrf_token,
            "user_joined_forums": joined_forums,
            "suggested_forums": suggested_forums,
            "current_endpoint": request.endpoint
        }

    def _is_valid_csrf():
        token = session.get("csrf_token", "")
        submitted = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        return bool(token and submitted and secrets.compare_digest(token, submitted))

    @app.before_request
    def csrf_protect():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Skip CSRF protection for all event-related routes
            if request.blueprint == "events":
                return
            # Skip CSRF protection for karaoke UI and API routes
            if request.path.startswith("/karaoke") or request.path.startswith("/api/"):
                return
            if request.endpoint and 'upload' in request.endpoint: # Loose check for upload endpoints
                 return
            if not _is_valid_csrf():
                flash("Invalid CSRF token. Please try again.", "error")
                return redirect(request.referrer or url_for("auth.index"))

    # Register Blueprints
    from auth import auth_bp
    from forum import forum_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(forum_bp)
    app.register_blueprint(event_bp)

    return app

# Create the app
app = create_app()

# Karaoke routes start:
# =============================================================================


@app.route("/karaoke")
@login_required
def karaoke():
    return karaoke_index()


@app.route("/karaoke/create")
@login_required
def karaoke_create():
    return create_session_page()


@app.route("/karaoke/join/<session_id>")
@login_required
def karaoke_join(session_id):
    session = SessionModel.query.filter_by(session_id=session_id).first()
    if not session:
        from flask import abort

        abort(404)

    return render_template("karaoke/join.html", session=session)


# This is used for the audio routing
@sock.route("/karaoke/ws/<session_id>")
def karaoke_ws(websocket, session_id):
    return audio_ws(websocket, session_id)


# get all the songs
@app.route("/api/songs", methods=["GET"])
@login_required
def api_get_songs():
    return get_songs()


# Add a song to the list
@app.route("/api/songs", methods=["POST"])
@login_required
def api_create_song():
    print("Post api songs called")
    data = request.get_json()
    return create_song(data)


# Get the song from the song id
@app.route("/api/songs/<int:song_id>", methods=["GET"])
@login_required
def api_get_song(song_id):
    print("Get song from id called")
    return get_song(song_id)


# get the songs lyrics
@app.route("/api/songs/<int:song_id>/lyrics", methods=["GET"])
@login_required
def api_get_song_lyrics(song_id):
    print("Get songs lyrics called")
    return get_song_lyrics(song_id)


# search for a song
@app.route("/api/songs/search", methods=["GET"])
@login_required
def api_search_songs():
    print("Get search songs called")
    query = request.args.get("q", "")
    return search_songs_external(query)


# add a song
@app.route("/api/songs/<int:song_id>", methods=["PUT"])
@login_required
def api_update_song(song_id):
    print("Put update songs called")
    data = request.get_json()
    return update_song(song_id, data)


# delete a song from the database
@app.route("/api/songs/<int:song_id>", methods=["DELETE"])
@login_required
def api_delete_song(song_id):
    return delete_song(song_id)


@app.route("/karaoke/songs/manage")
@login_required
def songs_manage():
    return render_template("karaoke/songs_manage.html")


@app.route("/api/sessions", methods=["POST"])
@login_required
def api_create_session():
    data = request.get_json()
    return create_karaoke_session(data)


@app.route("/api/sessions/<session_id>", methods=["GET"])
@login_required
def api_get_session(session_id):
    return get_session_info(session_id)


@app.route("/api/scores", methods=["POST"])
@login_required
def api_submit_score():
    data = request.get_json()
    return submit_score(data)


@app.route("/api/leaderboard", methods=["GET"])
@login_required
def api_get_leaderboard():
    limit = request.args.get("limit", 10, type=int)
    return get_leaderboard_data(limit)

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route("/api/queue", methods=["GET"])
@login_required
def api_get_queue():
    return get_song_queue()


@app.route("/api/queue/<session_id>", methods=["DELETE"])
@login_required
def api_delete_queue(session_id):
    return delete_queue_item(session_id)


@app.route("/api/user/ranking", methods=["GET"])
@login_required
def api_get_user_ranking():
    return get_user_ranking_data()


@app.route("/api/user/profile", methods=["GET"])
@login_required
def api_get_user_profile():
    user = g.current_user
    if not user:
        return jsonify({"error": "User not found"}), 404

    from database import get_user_stats, get_user_scores, get_recommended_songs

    stats = get_user_stats(user.id) or {}
    scores = get_user_scores(user.id, limit=100)

    def avg_or_zero(values):
        clean = [v for v in values if v is not None]
        if not clean:
            return 0
        return round(sum(clean) / len(clean), 1)

    pitch_accuracy = avg_or_zero([s.accuracy for s in scores])
    rhythm_accuracy = avg_or_zero([s.timing for s in scores])
    song_completion = avg_or_zero([s.completeness for s in scores])

    average_score = stats.get("average_score", 0)
    if isinstance(average_score, float):
        average_score = round(average_score, 1)

    # Favorite genres with counts
    genre_counts = {}
    for score in scores:
        if score.session and score.session.song and score.session.song.genre:
            genre = score.session.song.genre
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    favorite_genres = sorted(
        genre_counts.items(), key=lambda x: x[1], reverse=True
    )[:3]
    favorite_genres = [
        {"name": genre, "count": count, "icon": "music"}
        for genre, count in favorite_genres
    ]

    # Recent activity
    recent_activity = []
    for score in scores[:5]:
        if score.session and score.session.song:
            recent_activity.append(
                {
                    "song": score.session.song.title,
                    "artist": score.session.song.artist,
                    "score": score.score,
                    "date": score.created_at.strftime("%Y-%m-%d"),
                }
            )

    # Recommendations
    recommendations = []
    for song in get_recommended_songs(user.id, limit=5):
        recommendations.append(
            {
                "id": song.id,
                "title": song.title,
                "artist": song.artist,
                "difficulty": song.difficulty or "medium",
                "thumbnail": None,
            }
        )

    payload = {
        "stats": {
            "totalSessions": stats.get("total_sessions", 0),
            "totalSongs": stats.get("total_songs", 0),
            "highestScore": stats.get("highest_score", 0),
            "averageScore": average_score,
            "ranking": stats.get("ranking"),
            "improvementRate": stats.get("improvement_rate", 0),
        },
        "skills": {
            "pitchAccuracy": pitch_accuracy,
            "rhythmAccuracy": rhythm_accuracy,
            "vocalRange": average_score or 0,
            "songCompletion": song_completion,
        },
        "favoriteGenres": favorite_genres,
        "recentActivity": recent_activity,
        "recommendations": recommendations,
    }

    return jsonify(payload)


@app.route("/api/user/improvement", methods=["GET"])
@login_required
def api_get_user_improvement():
    user = g.current_user
    if not user:
        return jsonify([]), 200

    from database import get_user_improvement

    return jsonify(get_user_improvement(user.id))


@app.route("/api/user/sessions", methods=["GET"])
@login_required
def api_get_user_sessions():
    return get_user_sessions()


@app.route("/karaoke/leaderboard")
@login_required
def leaderboard_show():
    return render_template("karaoke/leaderboard.html")


@app.route("/karaoke/profile")
@login_required
def profile_view():
    return render_template("karaoke/profile.html")


@app.route("/karaoke/my-scores")
@login_required
def scores_my_scores():
    user = g.current_user
    if not user:
        flash("Please log in to view your scores.", "warning")
        return redirect(url_for("auth.login"))

    from database import get_user_scores

    scores = get_user_scores(user.id, limit=100)
    return render_template("karaoke/my_scores.html", scores=scores)


@app.route("/karaoke/scores/<int:score_id>/delete", methods=["POST"])
@login_required
def scores_delete_score(score_id):
    user = g.current_user
    if not user:
        flash("Please log in to manage your scores.", "warning")
        return redirect(url_for("auth.login"))

    score = Score.query.get(score_id)
    if not score or score.user_id != user.id:
        flash("Score not found or access denied.", "danger")
        return redirect(url_for("scores_my_scores"))

    db.session.delete(score)
    db.session.commit()
    flash("Score deleted.", "success")
    return redirect(url_for("scores_my_scores"))


# Karaoke routes end
# ============================================================================

project_root = os.path.dirname(__file__)


if __name__ == "__main__":
    socketio.run(app, debug=True, port=6000)
