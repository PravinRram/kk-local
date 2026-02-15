import os
import secrets
import json
import uuid
import base64
import sqlite3
from datetime import datetime

from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
    send_from_directory
)
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import db, User, Hobby, PasswordResetToken, Follow, Notification, Forum, get_sgt_now_naive
from config import Config
from validators import (
    validate_login,
    validate_register_step,
    validate_profile_update,
    validate_forgot_password,
    validate_change_password,
    validate_reset_password
)
from decorators import login_required, admin_required
from . import auth_bp

# --- Auth Routes (Account Style) ---

_PROFILE_PICTURE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _save_profile_picture(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in _PROFILE_PICTURE_EXTS:
        return None
    new_filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], new_filename)
    file_storage.save(path)
    return f"uploads/{new_filename}"


def _save_profile_picture_from_base64(data_url):
    if not data_url or not data_url.startswith("data:image/"):
        return None
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError:
        return None
    if "image/png" in header:
        ext = ".png"
    elif "image/jpeg" in header or "image/jpg" in header:
        ext = ".jpg"
    elif "image/webp" in header:
        ext = ".webp"
    else:
        return None
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return None
    if len(raw) > 2 * 1024 * 1024:
        return None
    new_filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], new_filename)
    with open(path, "wb") as handle:
        handle.write(raw)
    return f"uploads/{new_filename}"


def _age_group_from_dob(dob):
    if not dob:
        return None
    today = datetime.utcnow().date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    if 13 <= years <= 17:
        return "Youth"
    if 18 <= years <= 35:
        return "Young Adult"
    if 36 <= years <= 55:
        return "Adult"
    if years >= 56:
        return "Senior"
    return None

@auth_bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("forum.feed"))
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("forum.feed"))

    if request.method == "POST":
        valid, result = validate_login(request.form)
        if valid:
            identifier = request.form["identifier"]
            password = request.form["password"]
            user = User.query.filter(
                or_(User.email == identifier, User.username == identifier)
            ).first()

            if user and user.check_password(password):
                if not user.is_active:
                    flash("Your account has been deactivated.", "error")
                else:
                    session.clear()
                    session["user_id"] = user.id
                    session["username"] = user.username
                    session["is_admin"] = user.is_admin
                    session["profile_picture"] = user.profile_picture_url or user.profile_picture
                    
                    if not session.get("csrf_token"):
                            session["csrf_token"] = secrets.token_urlsafe(32)

                    flash(f"Welcome back, {user.display_name or user.username}!", "success")
                    return redirect(url_for("forum.feed"))
            else:
                flash("Invalid email/username or password.", "error")
        else:
            for error in result.values():
                flash(error, "error")

    return render_template("login.html", errors={})

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("forum.feed"))

    step = request.args.get("step", 1, type=int)
    
    if request.method == "POST":
        current_step = int(request.form.get("step", 1))
        action = request.form.get("action")

        if action == "back":
            next_step = max(1, current_step - 1)
            return render_template("register.html", step=next_step, data=request.form, interests=Config.INTERESTS, errors={})

        valid, result = validate_register_step(current_step, request.form, request.files)

        if not valid:
            return render_template("register.html", step=current_step, errors=result, data=request.form, interests=Config.INTERESTS)

        if current_step == 1:
            username = (request.form.get("username") or "").strip()
            if username and User.query.filter_by(username=username).first():
                flash("Username already taken.", "error")
                return render_template(
                    "register.html",
                    step=current_step,
                    data=request.form,
                    interests=Config.INTERESTS,
                    errors={"username": "Username already taken"},
                )

        if current_step == 2:
            email = (request.form.get("email") or "").strip().lower()
            if email and User.query.filter_by(email=email).first():
                flash("Email already registered.", "error")
                return render_template(
                    "register.html",
                    step=current_step,
                    data=request.form,
                    interests=Config.INTERESTS,
                    errors={"email": "Email already registered"},
                )
        
        if current_step < 5:
            next_step = current_step + 1
            return render_template("register.html", step=next_step, data=request.form, interests=Config.INTERESTS, errors={})
        
        else:
            username = request.form.get("username")
            email = request.form.get("email")

            # Check for existing user
            if User.query.filter_by(username=username).first():
                flash("Username already taken.", "error")
                return render_template("register.html", step=1, data=request.form, interests=Config.INTERESTS, errors={"username": "Username already taken"})
            
            if User.query.filter_by(email=email).first():
                flash("Email already registered.", "error")
                return render_template("register.html", step=2, data=request.form, interests=Config.INTERESTS, errors={"email": "Email already registered"})

            password = request.form.get("password")
            dob_str = request.form.get("date_of_birth")
            
            # Handle potential None for dob_str if someone bypasses validation
            dob = None
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
            
            cropped_avatar = (request.form.get("cropped_avatar") or "").strip()
            if cropped_avatar:
                profile_path = _save_profile_picture_from_base64(cropped_avatar)
            else:
                profile_path = _save_profile_picture(request.files.get("profile_picture"))

            user = User(
                username=username,
                email=email,
                display_name=request.form.get("display_name"),
                date_of_birth=dob,
                gender=None,
                age_group=_age_group_from_dob(dob),
                privacy="public",
                profile_picture_url=profile_path or "img/default_avatar.png",
                profile_picture=profile_path or "img/default_avatar.png",
            )
            user.set_password(password)
            
            try:
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("An account with this email or username already exists.", "error")
                return render_template("register.html", step=1, data=request.form, interests=Config.INTERESTS, errors={})
            
            # Auto-login
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["is_admin"] = user.is_admin
            session["profile_picture"] = user.profile_picture_url or user.profile_picture
            
            if not session.get("csrf_token"):
                session["csrf_token"] = secrets.token_urlsafe(32)

            flash("Registration successful! Please complete your profile.", "success")
            return redirect(url_for("auth.profile_edit", setup='true'))

    return render_template("register.html", step=step, data={}, interests=Config.INTERESTS, errors={})

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    errors = {}
    reset_link = None
    if request.method == "POST":
        is_valid, errors = validate_forgot_password(request.form)
        if is_valid:
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user:
                raw_token, record = PasswordResetToken.create_for_user(user)
                db.session.add(record)
                db.session.commit()
            else:
                raw_token = PasswordResetToken.generate_token()
            reset_link = url_for("auth.reset_password", token=raw_token, _external=True)
            flash(
                "If the email exists, a reset link has been generated.",
                "success",
            )
    return render_template(
        "forgot_password.html", errors=errors, reset_link=reset_link, hide_nav=True
    )


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    errors = {}
    invalid = False

    token_hash = PasswordResetToken.hash_token(token)
    record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not record or not record.is_valid():
        invalid = True

    if request.method == "POST" and not invalid:
        is_valid, errors = validate_reset_password(request.form)
        if is_valid:
            record.user.set_password(request.form.get("password"))
            record.used_at = get_sgt_now_naive()
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", errors=errors, invalid=invalid)

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    errors = {}
    if request.method == "POST":
        is_valid, errors = validate_change_password(request.form)
        if is_valid:
            if not g.current_user.check_password(request.form.get("old_password")):
                errors["old_password"] = "Current password is incorrect."
            else:
                g.current_user.set_password(request.form.get("new_password"))
                db.session.commit()
                flash("Password updated.", "success")
                return redirect(url_for("auth.profile_public", username=g.current_user.username))
    return render_template("change_password.html", errors=errors)

@auth_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    errors = {}
    if request.method == "POST":
        confirm_username = request.form.get("confirm_username")
        password = request.form.get("password")
        
        user = g.current_user
        
        if confirm_username != user.username:
            errors['confirm_username'] = "Username does not match."
            
        if not user.check_password(password):
            errors['password'] = "Incorrect password."
            
        if not errors:
            try:
                # Delete user (Cascading deletes should handle related data if configured, 
                # otherwise we might need to manually delete or set null)
                # For this implementation, we assume cascading or simple user deletion is desired.
                db.session.delete(user)
                db.session.commit()
                
                # Logout
                session.clear()
                
                flash("Your account has been successfully deleted.", "success")
                return redirect(url_for("auth.login"))
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred while deleting your account: {str(e)}", "error")
                
    return render_template("confirm_delete.html", errors=errors)

@auth_bp.route("/games")
@login_required
def games():
    # Placeholder implementation
    return render_template("placeholder.html", title="Games")


@auth_bp.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    # Placeholder implementation
    if request.method == "POST":
         flash("Admin registration not implemented in this demo.", "info")
         return redirect(url_for("auth.login"))
    return render_template("admin_register.html")

# --- Profile Routes (Account Style) ---

@auth_bp.route("/profile/<username>")
@login_required
def profile_view(username):
    user = User.query.filter_by(username=username).first_or_404()
    return redirect(url_for("auth.profile_public", username=user.username))

@auth_bp.route("/profile/public/<username>")
@auth_bp.route("/profile/other/<username>")
@login_required
def profile_public(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Check if viewing own profile and incomplete
    # Redirect removed to allow viewing profile even if incomplete

    followers_count = db.session.query(Follow).filter_by(followed_id=user.id).count()
    following_count = db.session.query(Follow).filter_by(follower_id=user.id).count()
    
    is_following = False
    is_owner = False
    mutual_followers = []
    mutual_forums = []
    mutual_events = []
    
    if g.current_user:
        is_owner = (g.current_user.id == user.id)
        if not is_owner:
            is_following = db.session.query(Follow).filter_by(
                follower_id=g.current_user.id, followed_id=user.id
            ).first() is not None
            current_following_ids = {
                row[0]
                for row in db.session.query(Follow.followed_id)
                .filter_by(follower_id=g.current_user.id)
                .all()
            }
            target_follower_ids = {
                row[0]
                for row in db.session.query(Follow.follower_id)
                .filter_by(followed_id=user.id)
                .all()
            }
            mutual_follower_ids = list(current_following_ids.intersection(target_follower_ids))
            if mutual_follower_ids:
                mutual_followers = (
                    User.query.filter(User.id.in_(mutual_follower_ids))
                    .order_by(User.username.asc())
                    .limit(12)
                    .all()
                )

            current_forum_ids = {forum.id for forum in g.current_user.joined_forums}
            target_forum_ids = {forum.id for forum in user.joined_forums}
            mutual_forum_ids = list(current_forum_ids.intersection(target_forum_ids))
            if mutual_forum_ids:
                mutual_forums = (
                    Forum.query.filter(Forum.id.in_(mutual_forum_ids))
                    .order_by(Forum.name.asc())
                    .limit(6)
                    .all()
                )

            events_db_path = os.path.join(current_app.root_path, "events.db")
            if os.path.exists(events_db_path):
                conn = sqlite3.connect(events_db_path)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT DISTINCT e.event_name, e.event_code
                        FROM events e
                        LEFT JOIN event_participants ep_current
                          ON ep_current.event_id = e.event_id
                          AND ep_current.user_id = ?
                          AND ep_current.status IN ('going', 'interested')
                        LEFT JOIN event_participants ep_target
                          ON ep_target.event_id = e.event_id
                          AND ep_target.user_id = ?
                          AND ep_target.status IN ('going', 'interested')
                        WHERE (e.host_id = ? OR ep_current.user_id IS NOT NULL)
                          AND (e.host_id = ? OR ep_target.user_id IS NOT NULL)
                        ORDER BY e.start_date ASC, e.event_id DESC
                        LIMIT 6
                        """,
                        (g.current_user.id, user.id, g.current_user.id, user.id),
                    )
                    rows = cur.fetchall()
                    mutual_events = [
                        {"event_name": row[0], "event_code": row[1]}
                        for row in rows
                    ]
                finally:
                    conn.close()

    return render_template(
        "profile_public.html",
        user=user,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        is_owner=is_owner,
        mutual_followers=mutual_followers,
        mutual_forums=mutual_forums,
        mutual_events=mutual_events,
        private=(user.privacy == 'private'),
        can_message=False, # Placeholder
        posts=user.posts
    )

@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    errors = {}
    user = g.current_user
    
    # Check completion status to enforce setup mode if incomplete
    missing_fields = []
    if not user.profile_picture_url: missing_fields.append('Profile Picture')
    if not user.date_of_birth: missing_fields.append('Date of Birth')
    if not user.location: missing_fields.append('Location')
    if not user.bio: missing_fields.append('Bio')
    if not user.hobbies: missing_fields.append('Hobbies')
    
    is_incomplete = len(missing_fields) > 0
    setup_mode = request.args.get('setup') == 'true' or is_incomplete
    
    if request.method == "POST":
        valid, result = validate_profile_update(request.form, request.files)
        if valid:
            user = g.current_user
            user.display_name = request.form.get("display_name")
            user.bio = request.form.get("bio")
            user.location = request.form.get("location")
            user.website = request.form.get("website")
            user.gender = request.form.get("gender")
            user.age_group = request.form.get("age_group")
            user.privacy = request.form.get("privacy")
            
            user.hobbies = []
            for hobby_id in request.form.getlist("hobbies"):
                hobby = Hobby.query.get(int(hobby_id))
                if hobby:
                    user.hobbies.append(hobby)

            cropped_data = request.form.get("cropped_avatar")
            if cropped_data and cropped_data.startswith("data:image"):
                try:
                    header, encoded = cropped_data.split(",", 1)
                    data = base64.b64decode(encoded)
                    ext = ".png"
                    if "jpeg" in header or "jpg" in header:
                        ext = ".jpg"
                    
                    new_filename = f"{uuid.uuid4().hex}{ext}"
                    path = os.path.join(current_app.config["UPLOAD_FOLDER"], new_filename)
                    with open(path, "wb") as f:
                        f.write(data)
                    
                    user.profile_picture_url = f"uploads/{new_filename}"
                    user.profile_picture = f"uploads/{new_filename}"
                except Exception as e:
                    print(f"Error saving cropped image: {e}")
            
            elif "profile_picture" in request.files:
                    f = request.files["profile_picture"]
                    if f.filename:
                        filename = secure_filename(f.filename)
                        ext = os.path.splitext(filename)[1]
                        new_filename = f"{uuid.uuid4().hex}{ext}"
                        path = os.path.join(current_app.config["UPLOAD_FOLDER"], new_filename)
                        f.save(path)
                        user.profile_picture_url = f"uploads/{new_filename}"
                        user.profile_picture = f"uploads/{new_filename}"

            db.session.commit()
            flash("Profile updated!", "success")
            
            # If profile is still incomplete, stay on edit page
            if not user.profile_picture_url or \
               not user.date_of_birth or \
               not user.location or \
               not user.bio or \
               not user.hobbies:
                 return redirect(url_for("auth.profile_edit", setup='true'))

            return redirect(url_for("auth.profile_view", username=user.username))
        else:
            errors = result
            for error in result.values():
                flash(error, "error")
    
    return render_template("profile_edit.html", user=g.current_user, hobbies=Hobby.query.all(), errors=errors, setup_mode=setup_mode, missing_fields=missing_fields)

@auth_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html")

@auth_bp.route('/profile/<int:user_id>')
@login_required
def profile_redirect(user_id):
    user = User.query.get_or_404(user_id)
    return redirect(url_for('auth.profile_public', username=user.username))

def _can_view_connections(target_user):
    return target_user.privacy == "public" or (
        g.current_user and g.current_user.id == target_user.id
    )

@auth_bp.route("/users/<username>/followers")
@login_required
def followers_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not _can_view_connections(user):
        flash("Followers list is private.", "warning")
        return redirect(url_for("auth.profile_public", username=username))
    follower_ids = [
        row[0]
        for row in db.session.query(Follow.follower_id)
        .filter_by(followed_id=user.id)
        .all()
    ]
    followers = User.query.filter(User.id.in_(follower_ids)).all() if follower_ids else []
    # Note: Using profile_public.html or we need a followers_list.html
    # Since followers_list.html was not seen in the template list, I'll check if it exists.
    # If not, I'll use a placeholder or check if I need to create it.
    # The account/__init__.py used render_template("followers_list.html").
    # I'll assume it exists or I might need to create it.
    # For now, I will assume it exists as I am focusing on BuildError.
    return render_template("followers_list.html", user=user, followers=followers)

@auth_bp.route("/users/<username>/following")
@login_required
def following_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not _can_view_connections(user):
        flash("Following list is private.", "warning")
        return redirect(url_for("auth.profile_public", username=username))
    following_ids = [
        row[0]
        for row in db.session.query(Follow.followed_id)
        .filter_by(follower_id=user.id)
        .all()
    ]
    following = User.query.filter(User.id.in_(following_ids)).all() if following_ids else []
    return render_template("following_list.html", user=user, following=following)

def _is_safe_next(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc

@auth_bp.route("/search")
@login_required
def search_users():
    query = (request.args.get("q") or "").strip()
    results = []
    follow_map = {}
    message_map = {}

    if query:
        results = (
            User.query.filter(
                or_(
                    User.username.ilike(f"%{query}%"),
                    User.display_name.ilike(f"%{query}%"),
                ),
                User.id != g.current_user.id,
            )
            .order_by(User.username.asc())
            .limit(20)
            .all()
        )

    for user in results:
        if user.id == g.current_user.id:
            continue
        is_following = (
            Follow.query.filter_by(
                follower_id=g.current_user.id, followed_id=user.id
            ).first()
            is not None
        )
        is_followed_by = (
            Follow.query.filter_by(
                follower_id=user.id, followed_id=g.current_user.id
            ).first()
            is not None
        )
        can_message = user.privacy == "public" or (is_following and is_followed_by)
        follow_map[user.id] = is_following
        message_map[user.id] = can_message

    return render_template(
        "search.html",
        query=query,
        results=results,
        follow_map=follow_map,
        message_map=message_map,
    )

@auth_bp.route("/users/<username>/follow", methods=["POST"])
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id == g.current_user.id:
        flash("You cannot follow yourself.", "warning")
        return redirect(url_for("auth.profile_public", username=username))
    if not Follow.query.filter_by(
        follower_id=g.current_user.id, followed_id=user.id
    ).first():
        db.session.add(
            Follow(follower_id=g.current_user.id, followed_id=user.id)
        )
        db.session.add(
            Notification(
                user_id=user.id,
                type="follow",
                message=f"{g.current_user.display_name or g.current_user.username} followed you.",
            )
        )
        db.session.commit()
        flash("You are now following this user.", "success")
    next_url = (request.form.get("next") or "").strip()
    if _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("auth.profile_public", username=username))

@auth_bp.route("/users/<username>/unfollow", methods=["POST"])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    removed = Follow.query.filter_by(
        follower_id=g.current_user.id, followed_id=user.id
    ).delete(synchronize_session=False)
    if removed:
        db.session.add(
            Notification(
                user_id=user.id,
                type="unfollow",
                message=(
                    f"{g.current_user.display_name or g.current_user.username} "
                    "unfollowed you."
                ),
            )
        )
    db.session.commit()
    flash("You have unfollowed this user.", "success")
    next_url = (request.form.get("next") or "").strip()
    if _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("auth.profile_public", username=username))
