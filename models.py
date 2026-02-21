import json
import secrets
import hashlib
from datetime import datetime, timedelta
import pytz
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

SGT = pytz.timezone('Asia/Singapore')

def get_sgt_now():
    return datetime.now(SGT)


def get_sgt_now_naive():
    return get_sgt_now().replace(tzinfo=None)

# Association Tables
user_hobbies = db.Table(
    "user_hobbies",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("hobby_id", db.Integer, db.ForeignKey("hobbies.id"), primary_key=True),
)

forum_members = db.Table('forum_members',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('forum_id', db.Integer, db.ForeignKey('forums.id', ondelete='CASCADE')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE')),
    db.Column('joined_at', db.DateTime, default=get_sgt_now)
)

forum_moderators = db.Table('forum_moderators',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('forum_id', db.Integer, db.ForeignKey('forums.id', ondelete='CASCADE')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE')),
    db.Column('added_at', db.DateTime, default=get_sgt_now)
)

# Models

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile Fields (Account)
    display_name = db.Column(db.String(40))
    bio = db.Column(db.Text) # Changed to Text for flexibility
    location = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    website = db.Column(db.String(255))
    profile_picture_url = db.Column(db.String(255)) # Account style
    profile_picture = db.Column(db.Text) # Forum style (base64 or url?) - keeping for compatibility
    
    privacy = db.Column(db.String(10), default="public")
    gender = db.Column(db.String(10))
    age_group = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    updated_at = db.Column(db.DateTime, default=get_sgt_now, onupdate=get_sgt_now)

    # Relationships (Account)
    hobbies = db.relationship("Hobby", secondary=user_hobbies, backref="users")
    
    # Relationships (Forum)
    created_forums = db.relationship('Forum', back_populates='creator', cascade='all, delete-orphan')
    joined_forums = db.relationship('Forum', secondary=forum_members, back_populates='members')
    moderated_forums = db.relationship('Forum', secondary=forum_moderators, back_populates='moderators')
    
    posts = db.relationship('Post', back_populates='user', cascade='all, delete-orphan')
    comments = db.relationship('Comment', back_populates='user', cascade='all, delete-orphan')
    likes = db.relationship('Like', back_populates='user', cascade='all, delete-orphan')
    
    # Merged Notification Relationship
    notifications = db.relationship('Notification', back_populates='user', cascade='all, delete-orphan')

    # Karaoke Relationships
    sessions = db.relationship(
        "SessionParticipant", back_populates="user", cascade="all, delete-orphan"
    )
    scores = db.relationship(
        "Score", back_populates="user", cascade="all, delete-orphan"
    )

    # Methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def public_dict(self):
        return {
            "username": self.username,
            "display_name": self.display_name,
            "bio": self.bio,
            "location": self.location,
            "website": self.website,
            "profile_picture_url": self.profile_picture_url,
            "privacy": self.privacy,
            "date_of_birth": self.date_of_birth,
            "created_at": self.created_at,
        }

    def to_dict(self):
        """Karaoke compatible to_dict"""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Hobby(db.Model):
    __tablename__ = 'hobbies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)

class Follow(db.Model):
    __tablename__ = 'follows' # Unified table name
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=get_sgt_now)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_sgt_now)

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    user = db.relationship("User", backref=db.backref("reset_tokens", lazy=True))

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def is_valid(self):
        if self.used_at is not None:
            return False
        if self.expires_at.tzinfo is None:
            return datetime.utcnow() <= self.expires_at
        return get_sgt_now() <= self.expires_at

    @classmethod
    def create_for_user(cls, user):
        raw_token = cls.generate_token()
        token_hash = cls.hash_token(raw_token)
        record = cls(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=get_sgt_now_naive() + timedelta(minutes=30),
        )
        return raw_token, record

# Forum Specific Models

class Forum(db.Model):
    __tablename__ = 'forums'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    rules = db.Column(db.Text)
    banner = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_private = db.Column(db.Boolean, default=False)
    interest_tags = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    updated_at = db.Column(db.DateTime, default=get_sgt_now, onupdate=get_sgt_now)
    
    # Relationships
    creator = db.relationship('User', back_populates='created_forums')
    posts = db.relationship('Post', back_populates='forum', cascade='all, delete-orphan')
    members = db.relationship('User', secondary=forum_members, back_populates='joined_forums')
    moderators = db.relationship('User', secondary=forum_moderators, back_populates='moderated_forums')
    bans = db.relationship('Ban', back_populates='forum', cascade='all, delete-orphan')

class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id', ondelete='CASCADE'))
    content = db.Column(db.String(280), nullable=False)
    image_url = db.Column(db.Text)
    hashtags = db.Column(db.Text)
    is_repost = db.Column(db.Boolean, default=False)
    original_post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE'))
    quote_content = db.Column(db.String(280))
    likes_count = db.Column(db.Integer, default=0)
    reposts_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    updated_at = db.Column(db.DateTime, default=get_sgt_now, onupdate=get_sgt_now)
    
    # Relationships
    user = db.relationship('User', back_populates='posts')
    forum = db.relationship('Forum', back_populates='posts')
    comments = db.relationship('Comment', back_populates='post', cascade='all, delete-orphan')
    likes = db.relationship('Like', back_populates='post', cascade='all, delete-orphan')

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.String(280), nullable=False)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    likes_count = db.Column(db.Integer, default=0)
    
    # Relationships
    post = db.relationship('Post', back_populates='comments')
    user = db.relationship('User', back_populates='comments')
    likes = db.relationship('CommentLike', back_populates='comment', cascade='all, delete-orphan')

class CommentLike(db.Model):
    __tablename__ = 'comment_likes'
    
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    
    comment = db.relationship('Comment', back_populates='likes')
    user = db.relationship('User')

class Like(db.Model):
    __tablename__ = 'likes'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    
    # Relationships
    post = db.relationship('Post', back_populates='likes')
    user = db.relationship('User', back_populates='likes')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False) # Merged content/message
    related_id = db.Column(db.Integer)
    read_at = db.Column(db.DateTime) # Used for is_read check
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    
    # Relationships
    user = db.relationship('User', back_populates='notifications')

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='SET NULL'))
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id', ondelete='SET NULL'))
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=get_sgt_now)

class Ban(db.Model):
    __tablename__ = 'bans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id', ondelete='CASCADE'), nullable=False)
    moderator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    appeal_status = db.Column(db.String(20), default='none')
    appeal_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    
    # Relationships
    forum = db.relationship('Forum', back_populates='bans')

class DeletedPost(db.Model):
    __tablename__ = 'deleted_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    original_post_id = db.Column(db.Integer, nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id', ondelete='SET NULL'))
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, default=get_sgt_now)

# Karaoke Models

class Song(db.Model):
    """Song library model"""

    __tablename__ = "songs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(200), nullable=False)
    genre = db.Column(db.String(50))
    duration = db.Column(db.Integer)  # Duration in seconds
    difficulty = db.Column(db.String(20))  # easy, medium, hard
    youtube_url = db.Column(db.String(500))
    audio_url = db.Column(db.String(500))  # Direct audio file URL (fallback)
    lyrics_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=get_sgt_now)

    # Relationships
    sessions = db.relationship("Session", back_populates="song")

    def __repr__(self):
        return f"<Song {self.title} by {self.artist}>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "genre": self.genre,
            "duration": self.duration,
            "difficulty": self.difficulty,
            "youtube_url": self.youtube_url,
            "lyrics_url": self.lyrics_url,
            "created_at": self.created_at.isoformat(),
        }


class Session(db.Model):
    """Karaoke session model"""

    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    song_id = db.Column(db.Integer, db.ForeignKey("songs.id"), nullable=False)
    status = db.Column(db.String(20), default="waiting")  # waiting, active, completed
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=get_sgt_now)

    # Relationships
    song = db.relationship("Song", back_populates="sessions")
    participants = db.relationship(
        "SessionParticipant", back_populates="session", cascade="all, delete-orphan"
    )
    scores = db.relationship(
        "Score", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Session {self.session_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "song": self.song.to_dict() if self.song else None,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat(),
            "participants": [p.to_dict() for p in self.participants],
        }


class SessionParticipant(db.Model):
    """Join table for session participants"""

    __tablename__ = "session_participants"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), default="singer")  # singer, duet_partner, audience
    joined_at = db.Column(db.DateTime, default=get_sgt_now)

    # Relationships
    session = db.relationship("Session", back_populates="participants")
    user = db.relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<SessionParticipant session={self.session_id} user={self.user_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user": self.user.to_dict() if self.user else None,
            "role": self.role,
            "joined_at": self.joined_at.isoformat(),
        }


class Score(db.Model):
    """Score/Leaderboard model"""

    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)  # Score out of 100
    mic_time = db.Column(db.Integer, default=0)  # Time in seconds with mic on
    accuracy = db.Column(db.Float)  # Pitch accuracy percentage
    timing = db.Column(db.Float)  # Timing accuracy percentage
    completeness = db.Column(db.Float)  # Song completion percentage
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_sgt_now)

    # Relationships
    session = db.relationship("Session", back_populates="scores")
    user = db.relationship("User", back_populates="scores")

    def __repr__(self):
        return f"<Score {self.score} for user={self.user_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user": self.user.to_dict() if self.user else None,
            "song": self.session.song.to_dict()
            if self.session and self.session.song
            else None,
            "score": self.score,
            "mic_time": self.mic_time,
            "accuracy": self.accuracy,
            "timing": self.timing,
            "completeness": self.completeness,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
