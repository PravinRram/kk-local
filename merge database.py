from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, scoped_session
from datetime import datetime
import json
import pytz

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
    Column('joined_at', DateTime, default=get_sgt_now())
)

forum_moderators = Table('forum_moderators', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('forum_id', Integer, ForeignKey('forums.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('added_at', DateTime, default=get_sgt_now())
)

follows = Table('follows', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('follower_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('following_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('created_at', DateTime, default=get_sgt_now())
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
    created_at = Column(DateTime, default=get_sgt_now())
    updated_at = Column(DateTime, default=get_sgt_now(), onupdate=get_sgt_now())
    
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
    created_at = Column(DateTime, default=get_sgt_now())
    updated_at = Column(DateTime, default=get_sgt_now(), onupdate=get_sgt_now())
    
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
    created_at = Column(DateTime, default=get_sgt_now())
    updated_at = Column(DateTime, default=get_sgt_now(), onupdate=get_sgt_now())
    
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
    created_at = Column(DateTime, default=get_sgt_now())
    
    # Relationships
    post = relationship('Post', back_populates='comments')
    user = relationship('User', back_populates='comments')

class Like(Base):
    __tablename__ = 'likes'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=get_sgt_now())
    
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
    created_at = Column(DateTime, default=get_sgt_now())
    
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
    created_at = Column(DateTime, default=get_sgt_now())

class Ban(Base):
    __tablename__ = 'bans'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='CASCADE'), nullable=False)
    moderator_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = Column(Text, nullable=False)
    appeal_status = Column(String(20), default='none')  # none, pending, approved, rejected
    appeal_text = Column(Text)
    created_at = Column(DateTime, default=get_sgt_now())
    
    # Relationships
    forum = relationship('Forum', back_populates='bans')

class DeletedPost(Base):
    __tablename__ = 'deleted_posts'
    
    id = Column(Integer, primary_key=True)
    original_post_id = Column(Integer, nullable=False)
    forum_id = Column(Integer, ForeignKey('forums.id', ondelete='SET NULL'))
    deleted_by = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = Column(Text)
    deleted_at = Column(DateTime, default=get_sgt_now())

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