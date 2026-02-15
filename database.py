from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Table, func, desc, or_
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, scoped_session
from datetime import datetime, timedelta
import json
import pytz
import random

# Import models for logic functions
from models import db, Song, Session, SessionParticipant, Score
from models import User as AppUser

SGT = pytz.timezone('Asia/Singapore')

def get_sgt_now():
    return datetime.now(SGT)

class Base(DeclarativeBase):
    pass

# Association tables for many-to-many relationships
forum_members = Table('forum_members', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('forum_id', Integer, ForeignKey('forums.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('joined_at', DateTime, default=get_sgt_now)
)

forum_moderators = Table('forum_moderators', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('forum_id', Integer, ForeignKey('forums.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('added_at', DateTime, default=get_sgt_now)
)

follows = Table('follows', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('follower_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('following_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('created_at', DateTime, default=get_sgt_now)
)

# Models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    birthdate = Column(Date, nullable=False)
    profile_picture = Column(Text)
    interests = Column(Text)  # JSON string
    bio = Column(Text)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_sgt_now)
    updated_at = Column(DateTime, default=get_sgt_now, onupdate=get_sgt_now)
    
    # Relationships
    posts = relationship('Post', back_populates='user', cascade='all, delete-orphan')
    comments = relationship('Comment', back_populates='user', cascade='all, delete-orphan')
    notifications = relationship('Notification', back_populates='user', cascade='all, delete-orphan')
    created_forums = relationship('Forum', back_populates='creator', cascade='all, delete-orphan')
    
    # Many-to-many relationships
    joined_forums = relationship('Forum', secondary=forum_members, back_populates='members')
    moderated_forums = relationship('Forum', secondary=forum_moderators, back_populates='moderators')
    followers = relationship('User', secondary=follows,
                           primaryjoin=id == follows.c.following_id,
                           secondaryjoin=id == follows.c.follower_id,
                           backref='following')

class Forum(Base):
    __tablename__ = 'forums'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    rules = Column(Text)
    banner = Column(Text)
    creator_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_private = Column(Boolean, default=False)
    interest_tags = Column(Text)  # JSON string
    created_at = Column(DateTime, default=get_sgt_now)
    updated_at = Column(DateTime, default=get_sgt_now, onupdate=get_sgt_now)
    
    # Relationships
    creator = relationship('User', back_populates='created_forums')
    posts = relationship('Post', back_populates='forum', cascade='all, delete-orphan')
    members = relationship('User', secondary=forum_members, back_populates='joined_forums')
    moderators = relationship('User', secondary=forum_moderators, back_populates='moderated_forums')
    bans = relationship('Ban', back_populates='forum', cascade='all, delete-orphan')

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='CASCADE'))
    content = Column(String(280), nullable=False)
    image_url = Column(Text)
    hashtags = Column(Text)
    is_repost = Column(Boolean, default=False)
    original_post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'))
    quote_content = Column(String(280))
    likes_count = Column(Integer, default=0)
    reposts_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_sgt_now)
    updated_at = Column(DateTime, default=get_sgt_now, onupdate=get_sgt_now)
    
    # Relationships
    user = relationship('User', back_populates='posts')
    forum = relationship('Forum', back_populates='posts')
    comments = relationship('Comment', back_populates='post', cascade='all, delete-orphan')
    likes = relationship('Like', back_populates='post', cascade='all, delete-orphan')

class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = Column(String(280), nullable=False)
    created_at = Column(DateTime, default=get_sgt_now)
    
    # Relationships
    post = relationship('Post', back_populates='comments')
    user = relationship('User', back_populates='comments')

class Like(Base):
    __tablename__ = 'likes'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=get_sgt_now)
    
    # Relationships
    post = relationship('Post', back_populates='likes')

class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False)  # reply, mention, forum_activity, etc.
    content = Column(Text, nullable=False)
    related_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_sgt_now)
    
    # Relationships
    user = relationship('User', back_populates='notifications')

class Report(Base):
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True)
    reporter_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reported_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    post_id = Column(Integer, ForeignKey('posts.id', ondelete='SET NULL'))
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='SET NULL'))
    reason = Column(Text, nullable=False)
    status = Column(String(20), default='pending')  # pending, reviewed, resolved
    created_at = Column(DateTime, default=get_sgt_now)

class Ban(Base):
    __tablename__ = 'bans'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='CASCADE'), nullable=False)
    moderator_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = Column(Text, nullable=False)
    appeal_status = Column(String(20), default='none')  # none, pending, approved, rejected
    appeal_text = Column(Text)
    created_at = Column(DateTime, default=get_sgt_now)
    
    # Relationships
    forum = relationship('Forum', back_populates='bans')

class DeletedPost(Base):
    __tablename__ = 'deleted_posts'
    
    id = Column(Integer, primary_key=True)
    original_post_id = Column(Integer, nullable=False)
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='SET NULL'))
    deleted_by = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = Column(Text)
    deleted_at = Column(DateTime, default=get_sgt_now)

# Database initialization
class Database:
    def __init__(self, db_uri='sqlite:///kampongkonek.db'):
        self.engine = create_engine(db_uri, connect_args={'check_same_thread': False})
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
    def init_db(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        
    def get_session(self):
        """Get a new session"""
        return self.Session()
        
    def close_session(self):
        """Close the session"""
        self.Session.remove()

# Logic functions from database.py

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_initial_data()


def seed_initial_data():
    """Seed the database with initial data for demos/dev"""
    seed_default_songs()

        # Create some sample users
    if AppUser.query.count() == 0:
        sample_users = [
            {"username": "elder_joe", "display_name": "Uncle Joe"},
            {"username": "grandma_sally", "display_name": "Grandma Sally"},
            {"username": "young_tim", "display_name": "Tim"},
            {"username": "aunt_may", "display_name": "Auntie May"},
            {"username": "uncle_ben", "display_name": "Uncle Benjamin"},
        ]

        for user_data in sample_users:
            # Add default values for required fields not in sample_users
            user_data['email'] = f"{user_data['username']}@example.com"
            user_data['password'] = "password123" # Models.User uses set_password, but if we init directly we might need password field logic. 
            # Wait, AppUser (models.User) has set_password method but password_hash column.
            # If we init with **user_data, we need to handle password.
            # AppUser likely doesn't accept 'password' in constructor if it's not a column? 
            # Actually db.Model constructor accepts kwargs for columns.
            # We need to set password_hash.
            
            # Let's fix this properly
            u = AppUser(
                username=user_data['username'],
                display_name=user_data['display_name'],
                email=f"{user_data['username']}@example.com"
            )
            u.set_password('password123')
            db.session.add(u)

        db.session.commit()
        print(f"Seeded {len(sample_users)} users into the database")

        # Create some sample sessions and scores
        seed_sample_sessions_and_scores()


DEFAULT_SONGS = [
    {
        "title": "Yesterday",
        "artist": "The Beatles",
        "genre": "Pop",
        "duration": 143,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=wXTJBr9tt8Q",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/beatles/yesterday.html",
    },
    {
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "genre": "Rock",
        "duration": 354,
        "difficulty": "hard",
        "youtube_url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/queen/bohemianrhapsody.html",
    },
    {
        "title": "Let It Be",
        "artist": "The Beatles",
        "genre": "Pop",
        "duration": 243,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=QDYfEBY9NM4",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/beatles/letitbe.html",
    },
    {
        "title": "Sweet Child O Mine",
        "artist": "Guns N Roses",
        "genre": "Rock",
        "duration": 356,
        "difficulty": "medium",
        "youtube_url": "https://www.youtube.com/watch?v=1w7OgIMMRc4",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/gunsnroses/sweetchildomine.html",
    },
    {
        "title": "Wonderful Tonight",
        "artist": "Eric Clapton",
        "genre": "Rock",
        "duration": 218,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=vUSzL2leZGE",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/ericclapton/wonderfultonight.html",
    },
    {
        "title": "I Will Always Love You",
        "artist": "Whitney Houston",
        "genre": "Pop",
        "duration": 273,
        "difficulty": "hard",
        "youtube_url": "https://www.youtube.com/watch?v=3JWTaaS7LdU",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/whitneyhouston/iwillalwaysloveyou.html",
    },
    {
        "title": "Stand By Me",
        "artist": "Ben E. King",
        "genre": "Soul",
        "duration": 179,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=hwZNL7QVJjE",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/beneking/standbyme.html",
    },
    {
        "title": "Hotel California",
        "artist": "Eagles",
        "genre": "Rock",
        "duration": 391,
        "difficulty": "medium",
        "youtube_url": "https://www.youtube.com/embed/09839DpTctU?si=Jsz-j9mXT3R9Lzav",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/eagles/hotelcalifornia.html",
    },
    {
        "title": "Billie Jean",
        "artist": "Michael Jackson",
        "genre": "Pop",
        "duration": 294,
        "difficulty": "medium",
        "youtube_url": "https://www.youtube.com/watch?v=Zi_XLOBDo_Y",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/michaeljackson/billiejean.html",
    },
    {
        "title": "My Way",
        "artist": "Frank Sinatra",
        "genre": "Jazz",
        "duration": 275,
        "difficulty": "medium",
        "youtube_url": "https://www.youtube.com/watch?v=qQzdAsjWGPg",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/franksinatra/myway.html",
    },
    {
        "title": "Lean On Me",
        "artist": "Bill Withers",
        "genre": "Soul",
        "duration": 254,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=fOZ-MySzAac",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/billwithers/leanonme.html",
    },
    {
        "title": "Respect",
        "artist": "Aretha Franklin",
        "genre": "Soul",
        "duration": 147,
        "difficulty": "medium",
        "youtube_url": "https://www.youtube.com/watch?v=6FOUqQt3Kg0",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/arethafranklin/respect.html",
    },
    {
        "title": "Home on the Range",
        "artist": "Traditional",
        "genre": "Country",
        "duration": 132,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=MVRi9XlT4tk",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/traditionalsong/homeontherange.html",
    },
    {
        "title": "Fly Me To The Moon",
        "artist": "Frank Sinatra",
        "genre": "Jazz",
        "duration": 147,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=ZEcqHA7dbwM",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/franksinatra/flymetothemoon.html",
    },
    {
        "title": "You Are My Sunshine",
        "artist": "Traditional",
        "genre": "Country",
        "duration": 180,
        "difficulty": "easy",
        "youtube_url": "https://www.youtube.com/watch?v=cGa3zFRqDn4",
        "audio_url": None,
        "lyrics_url": "https://www.azlyrics.com/lyrics/traditionalsong/youaremysunshine.html",
    },
]


def seed_default_songs():
    """Ensure the default song list exists (idempotent)."""
    existing = {
        (title, artist)
        for title, artist in Song.query.with_entities(Song.title, Song.artist).all()
    }

    to_add = []
    for song_data in DEFAULT_SONGS:
        key = (song_data["title"], song_data["artist"])
        if key not in existing:
            to_add.append(Song(**song_data))

    if not to_add:
        return

    db.session.add_all(to_add)
    db.session.commit()
    print(f"Seeded {len(to_add)} default songs into the database")


def seed_sample_sessions_and_scores():
    """Seed some sample sessions and scores for demo purposes"""
    users = AppUser.query.all()
    songs = Song.query.all()

    if not users or not songs:
        return

    # Create 10 sample completed sessions with scores
    for _ in range(10):
        user = random.choice(users)
        song = random.choice(songs)

        # Create session (completed)
        session_id = f"sample-{str(random.randint(10000, 99999))}"
        created_at = get_sgt_now() - timedelta(days=random.randint(1, 30))

        session = Session(
            session_id=session_id,
            song_id=song.id,
            status="completed",
            created_at=created_at,
            started_at=created_at + timedelta(minutes=random.randint(1, 5)),
            completed_at=created_at + timedelta(minutes=random.randint(10, 20)),
        )
        db.session.add(session)
        db.session.flush()  # Flush to get session ID

        # Add participant
        participant = SessionParticipant(
            session_id=session.id, user_id=user.id, role="singer", joined_at=created_at
        )
        db.session.add(participant)

        # Add score with random mic time (30 seconds to 5 minutes)
        base_score = random.randint(70, 95)
        mic_time = random.randint(30, 300)  # 30 seconds to 5 minutes
        score = Score(
            session_id=session.id,
            user_id=user.id,
            score=base_score,
            mic_time=mic_time,
            accuracy=base_score + random.randint(-5, 5),
            timing=base_score + random.randint(-5, 5),
            completeness=base_score + random.randint(-10, 10),
            created_at=session.completed_at,
        )
        db.session.add(score)

    db.session.commit()
    print(f"Seeded 10 sample sessions with scores")


def get_or_create_user(username, display_name=None):
    """Get existing user or create new one"""
    user = AppUser.query.filter_by(username=username).first()
    if not user:
        user = AppUser(username=username, display_name=display_name or username, email=f"{username}@example.com")
        user.set_password("password123") # Default password for auto-created users
        db.session.add(user)
        db.session.commit()
    elif display_name and user.display_name != display_name:
        # Update display name if provided and different
        user.display_name = display_name
        db.session.commit()
    return user


def create_session(session_id, song_id):
    """Create a new karaoke session"""
    session = Session(session_id=session_id, song_id=song_id, status="waiting")
    db.session.add(session)
    db.session.commit()
    return session


def add_participant_to_session(session_id, user_id, role="singer"):
    """Add a participant to a session"""
    session = Session.query.filter_by(session_id=session_id).first()
    if not session:
        return None

    # Check if user is already in this session
    existing = SessionParticipant.query.filter_by(
        session_id=session.id, user_id=user_id
    ).first()

    if existing:
        return existing

    participant = SessionParticipant(session_id=session.id, user_id=user_id, role=role)
    db.session.add(participant)
    db.session.commit()
    return participant


def save_score(
    session_id,
    user_id,
    score,
    mic_time=0,
    accuracy=None,
    timing=None,
    completeness=None,
    notes=None,
):
    """Save a score for a user in a session"""
    session = Session.query.filter_by(session_id=session_id).first()
    if not session:
        return None

    score_entry = Score(
        session_id=session.id,
        user_id=user_id,
        score=score,
        mic_time=mic_time,
        accuracy=accuracy,
        timing=timing,
        completeness=completeness,
        notes=notes,
    )
    db.session.add(score_entry)
    db.session.commit()
    return score_entry


def get_leaderboard(limit=10, period=None):
    """Get top users by total karaoke time with optional time period filter

    period: 'week', 'month', 'year', or None (all time)
    Returns list of dicts with user info and total mic time
    """
    query = (
        db.session.query(
            AppUser,
            func.sum(Score.mic_time).label("total_mic_time"),
            func.count(Score.id).label("session_count"),
        )
        .select_from(AppUser)
        .join(Score, Score.user_id == AppUser.id)
        .group_by(AppUser.id)
    )

    # Apply time period filter if specified
    if period:
        now = get_sgt_now()
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now.replace(day=1)
        elif period == "year":
            start_date = now.replace(month=1, day=1)
        else:
            start_date = None

        if start_date:
            query = query.filter(Score.created_at >= start_date)

    results = query.order_by(desc("total_mic_time")).limit(limit).all()

    # Format results as list of dicts with user and time info
    leaderboard_data = []
    for user, total_time, session_count in results:
        leaderboard_data.append(
            {
                "user": user,
                "total_mic_time": total_time or 0,
                "session_count": session_count,
                "created_at": user.created_at,  # Use user creation date for display
            }
        )

    return leaderboard_data


def get_user_scores(user_id, limit=10):
    """Get scores for a specific user"""
    return (
        Score.query.filter_by(user_id=user_id)
        .order_by(Score.created_at.desc())
        .limit(limit)
        .all()
    )


def get_song_leaderboard(song_id, limit=5):
    """Get top scores for a specific song"""
    return (
        Score.query.join(Session)
        .filter(Session.song_id == song_id)
        .order_by(Score.score.desc())
        .limit(limit)
        .all()
    )


def get_user_stats(user_id):
    """Get statistics for a user"""
    user = AppUser.query.get(user_id)
    if not user:
        return None

    scores = Score.query.filter_by(user_id=user_id).all()
    if not scores:
        return {
            "user": user.to_dict(),
            "total_sessions": 0,
            "average_score": 0,
            "highest_score": 0,
            "total_songs": 0,
            "favorite_genres": [],
            "improvement_rate": 0,
            "ranking": None,
        }

    # Count unique songs
    unique_song_ids = set()
    for score in scores:
        if score.session and score.session.song:
            unique_song_ids.add(score.session.song_id)

    # Calculate improvement rate (average of last 3 scores vs first 3 scores)
    chronological_scores = sorted(scores, key=lambda s: s.created_at)
    first_scores = (
        chronological_scores[:3]
        if len(chronological_scores) >= 3
        else chronological_scores
    )
    last_scores = (
        chronological_scores[-3:]
        if len(chronological_scores) >= 3
        else chronological_scores
    )

    avg_first = (
        sum(s.score for s in first_scores) / len(first_scores) if first_scores else 0
    )
    avg_last = (
        sum(s.score for s in last_scores) / len(last_scores) if last_scores else 0
    )

    improvement_rate = 0
    if avg_first > 0:
        improvement_rate = ((avg_last - avg_first) / avg_first) * 100

    # Find favorite genres (most played)
    genre_counts = {}
    for score in scores:
        if score.session and score.session.song:
            genre = score.session.song.genre
            if genre in genre_counts:
                genre_counts[genre] += 1
            else:
                genre_counts[genre] = 1

    # Sort genres by count and get top 3
    favorite_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    favorite_genres = [genre for genre, count in favorite_genres]

    # Get user global ranking
    user_best_score = max(s.score for s in scores)
    better_users = (
        Score.query.filter(Score.score > user_best_score)
        .with_entities(Score.user_id)
        .distinct()
        .count()
    )
    ranking = better_users + 1  # Add 1 to convert from 0-indexed to 1-indexed ranking

    return {
        "user": user.to_dict(),
        "total_sessions": len(scores),
        "average_score": sum(s.score for s in scores) / len(scores),
        "highest_score": max(s.score for s in scores),
        "total_songs": len(unique_song_ids),
        "favorite_genres": favorite_genres,
        "improvement_rate": round(improvement_rate, 1),
        "ranking": ranking,
    }


def get_monthly_top_players(limit=3):
    """Get top players for the current month based on number of sessions played"""
    now = get_sgt_now()
    first_day_of_month = datetime(now.year, now.month, 1)

    result = (
        db.session.query(
            AppUser,
            func.count(Score.id).label("session_count"),
            func.avg(Score.score).label("avg_score"),
            func.max(Score.score).label("max_score"),
        )
        .join(Score)
        .filter(Score.created_at >= first_day_of_month)
        .group_by(AppUser.id)
        .order_by(func.count(Score.id).desc(), func.avg(Score.score).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "user": user.to_dict(),
            "session_count": session_count,
            "avg_score": round(avg_score, 1) if avg_score else 0,
            "max_score": max_score,
        }
        for user, session_count, avg_score, max_score in result
    ]


def get_recommended_songs(user_id, limit=5):
    """Get song recommendations for a user based on past performance and preferences"""
    user = AppUser.query.get(user_id)
    if not user:
        return []

    # Get user's previously sung songs
    user_scores = Score.query.filter_by(user_id=user_id).all()
    sung_song_ids = set()

    if not user_scores:
        # For new users without history, recommend easy songs
        return (
            Song.query.filter_by(difficulty="easy")
            .order_by(func.random())
            .limit(limit)
            .all()
        )

    # Determine favorite genres and difficulties based on history
    genre_scores = {}
    difficulty_scores = {}

    for score in user_scores:
        if score.session and score.session.song:
            song = score.session.song
            sung_song_ids.add(song.id)

            # Track genres user performs well in
            if song.genre not in genre_scores:
                genre_scores[song.genre] = []
            genre_scores[song.genre].append(score.score)

            # Track difficulties user performs well in
            if song.difficulty not in difficulty_scores:
                difficulty_scores[song.difficulty] = []
            difficulty_scores[song.difficulty].append(score.score)

    # Calculate average scores for each genre and difficulty
    avg_genre_scores = {
        genre: sum(scores) / len(scores) for genre, scores in genre_scores.items()
    }
    avg_difficulty_scores = {
        diff: sum(scores) / len(scores) for diff, scores in difficulty_scores.items()
    }

    # Find top performing genre and appropriate difficulty
    top_genre = (
        max(avg_genre_scores.items(), key=lambda x: x[1])[0]
        if avg_genre_scores
        else None
    )

    # Determine appropriate difficulty level based on performance
    if avg_difficulty_scores:
        best_difficulty_score = max(avg_difficulty_scores.items(), key=lambda x: x[1])
        if (
            best_difficulty_score[1] >= 85
        ):  # If user scores well in their best difficulty
            # Suggest songs of same or slightly harder difficulty
            if best_difficulty_score[0] == "easy":
                target_difficulties = ["easy", "medium"]
            elif best_difficulty_score[0] == "medium":
                target_difficulties = ["medium", "hard"]
            else:
                target_difficulties = ["hard"]
        else:
            # If user isn't scoring well, suggest same or easier difficulty
            if best_difficulty_score[0] == "hard":
                target_difficulties = ["medium", "hard"]
            elif best_difficulty_score[0] == "medium":
                target_difficulties = ["easy", "medium"]
            else:
                target_difficulties = ["easy"]
    else:
        target_difficulties = ["easy", "medium"]

    # Build query based on preferences
    query = Song.query.filter(~Song.id.in_(sung_song_ids) if sung_song_ids else True)

    if top_genre:
        # 70% chance to recommend songs from favorite genre
        if random.random() < 0.7:
            query = query.filter(Song.genre == top_genre)

    query = query.filter(Song.difficulty.in_(target_difficulties))

    # Get recommendations
    recommendations = query.order_by(func.random()).limit(limit).all()

    # If not enough recommendations, fill with random songs they haven't sung
    if len(recommendations) < limit:
        remaining = limit - len(recommendations)
        existing_ids = [song.id for song in recommendations]
        additional = (
            Song.query.filter(
                ~Song.id.in_(list(sung_song_ids) + existing_ids)
                if sung_song_ids or existing_ids
                else True
            )
            .order_by(func.random())
            .limit(remaining)
            .all()
        )

        recommendations.extend(additional)

    return recommendations


def search_songs(search_term, genre=None, difficulty=None, limit=20):
    """Search for songs with filtering options"""
    query = Song.query

    if search_term:
        query = query.filter(
            or_(
                Song.title.ilike(f"%{search_term}%"),
                Song.artist.ilike(f"%{search_term}%"),
            )
        )

    if genre:
        query = query.filter(Song.genre == genre)

    if difficulty:
        query = query.filter(Song.difficulty == difficulty)

    return query.order_by(Song.title).limit(limit).all()


def get_user_improvement(user_id):
    """Get user's improvement over time for visualization"""
    scores = Score.query.filter_by(user_id=user_id).order_by(Score.created_at).all()

    if not scores:
        return []

    result = []
    for score in scores:
        result.append(
            {
                "date": score.created_at.strftime("%Y-%m-%d"),
                "score": score.score,
                "song_title": score.session.song.title
                if score.session and score.session.song
                else "Unknown",
                "metrics": {
                    "accuracy": score.accuracy,
                    "timing": score.timing,
                    "completeness": score.completeness,
                },
            }
        )

    return result


def get_user_ranking(user_id):
    """Get user's ranking based on total karaoke time"""
    user = AppUser.query.get(user_id)
    if not user:
        return None

    # Get user's total mic time and stats
    user_stats = (
        db.session.query(
            func.sum(Score.mic_time).label("total_mic_time"),
            func.count(Score.id).label("total_sessions"),
            func.avg(Score.score).label("avg_score"),
            func.max(Score.score).label("highest_score"),
        )
        .filter(Score.user_id == user_id)
        .first()
    )

    if not user_stats or not user_stats.total_mic_time:
        return {
            "ranking": None,
            "total_mic_time": 0,
            "total_sessions": 0,
            "avg_score": 0,
            "highest_score": 0,
        }

    # Calculate ranking based on total mic time
    # Count users with more total mic time
    better_users_count = (
        db.session.query(Score.user_id)
        .group_by(Score.user_id)
        .having(func.sum(Score.mic_time) > user_stats.total_mic_time)
        .count()
    )

    ranking = better_users_count + 1

    return {
        "ranking": ranking,
        "total_mic_time": int(user_stats.total_mic_time or 0),
        "total_sessions": user_stats.total_sessions,
        "avg_score": round(float(user_stats.avg_score or 0), 1),
        "highest_score": int(user_stats.highest_score or 0),
    }


def get_user_active_sessions(user_id):
    """Get user's active or waiting sessions"""
    sessions = (
        Session.query.join(SessionParticipant)
        .filter(
            SessionParticipant.user_id == user_id,
            Session.status.in_(["waiting", "active"]),
        )
        .order_by(Session.created_at.desc())
        .all()
    )

    return sessions


def get_community_stats():
    """Get overall community statistics"""
    total_users = AppUser.query.count()
    total_sessions = Session.query.count()
    total_songs = Song.query.count()

    # Average score
    avg_score_result = db.session.query(func.avg(Score.score)).scalar()
    avg_score = round(avg_score_result, 1) if avg_score_result else 0

    # Most popular songs
    popular_songs_result = (
        db.session.query(Song, func.count(Session.id).label("session_count"))
        .join(Session)
        .group_by(Song.id)
        .order_by(desc("session_count"))
        .limit(5)
        .all()
    )

    popular_songs = [
        {"song": song.to_dict(), "session_count": session_count}
        for song, session_count in popular_songs_result
    ]

    # Most popular genres
    genre_counts = (
        db.session.query(Song.genre, func.count(Session.id).label("count"))
        .join(Session)
        .group_by(Song.genre)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    genres = [{"genre": genre, "count": count} for genre, count in genre_counts]

    # Activity by time of day (last 30 days)
    thirty_days_ago = get_sgt_now() - timedelta(days=30)
    time_data = (
        db.session.query(
            func.extract("hour", Session.created_at).label("hour"),
            func.count(Session.id).label("count"),
        )
        .filter(Session.created_at >= thirty_days_ago)
        .group_by("hour")
        .all()
    )

    hourly_activity = [{"hour": int(hour), "count": count} for hour, count in time_data]

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_songs": total_songs,
        "avg_score": avg_score,
        "popular_songs": popular_songs,
        "popular_genres": genres,
        "hourly_activity": hourly_activity,
    }
