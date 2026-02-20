from models import User, Forum, Post, Comment, Like, Notification, Ban, Follow, Hobby, forum_members, forum_moderators
# from database import User, Forum, Post, Comment, Like, Notification, Ban, follows, forum_members
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import or_, and_, desc, func
import json
import pytz

SGT = pytz.timezone('Asia/Singapore')

def get_sgt_now():
    return datetime.now(SGT)

class UserService:
    def __init__(self, session):
        self.session = session
    
    def validate_registration(self, username, email, password, birthdate, interests=None):
        errors = []
        if not username or len(username) < 3 or len(username) > 50:
            errors.append("Username must be between 3 and 50 characters")
        if not email or '@' not in email or len(email) > 100:
            errors.append("Valid email is required")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters")
        try:
            birth_date = datetime.strptime(birthdate, '%Y-%m-%d')
            birth_date = SGT.localize(birth_date)
            age = (get_sgt_now() - birth_date).days / 365.25
            if age < 13:
                errors.append("Must be at least 13 years old")
            if age > 100:
                errors.append("Age cannot exceed 100 years")
        except ValueError:
            errors.append("Invalid birthdate format")
        if not interests or len(interests) == 0:
            errors.append("Please select at least one interest")
        if self.session.query(User).filter_by(username=username).first():
            errors.append("Username already exists")
        if self.session.query(User).filter_by(email=email).first():
            errors.append("Email already exists")
        return errors
    
    def create(self, username, email, password, birthdate, interests, profile_picture='img/default_avatar.png', bio=''):
        password_hash = generate_password_hash(password)
        interests_json = json.dumps(interests) if interests else json.dumps([])
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            date_of_birth=datetime.strptime(birthdate, '%Y-%m-%d').date(),
            # birthdate=datetime.strptime(birthdate, '%Y-%m-%d').date(),
            # interests=interests_json, # Removed as it's not in User model
            profile_picture=profile_picture,
            bio=bio
        )
        
        # Save interests as hobbies
        if interests:
            for interest_name in interests:
                hobby = self.session.query(Hobby).filter_by(name=interest_name).first()
                if hobby:
                    user.hobbies.append(hobby)
                    
        self.session.add(user)
        self.session.commit()
        return user.id
    
    def update(self, user_id, username=None, birthdate=None, profile_picture=None, bio=None, interests=None):
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        if username and username != user.username:
            existing = self.session.query(User).filter_by(username=username).first()
            if existing and existing.id != user_id:
                return False
            user.username = username
        if birthdate:
            if isinstance(birthdate, str):
                user.date_of_birth = datetime.strptime(birthdate, '%Y-%m-%d').date()
            else:
                user.date_of_birth = birthdate
        if profile_picture is not None:
            user.profile_picture = profile_picture if profile_picture.strip() else 'img/default_avatar.png'
        if bio is not None:
            user.bio = bio
        if interests is not None:
            # Clear existing hobbies
            user.hobbies = []
            # Add new hobbies
            for interest_name in interests:
                hobby = self.session.query(Hobby).filter_by(name=interest_name).first()
                if hobby:
                    user.hobbies.append(hobby)
        user.updated_at = get_sgt_now()
        self.session.commit()
        return True

    def validate_update(self, user_id, username, birthdate, interests=None):
        errors = []
        if username and (len(username) < 3 or len(username) > 50):
            errors.append("Username must be between 3 and 50 characters")
        if username:
            existing = self.session.query(User).filter_by(username=username).first()
            if existing and existing.id != user_id:
                errors.append("Username already taken")
        if birthdate:
            try:
                birth_date = datetime.strptime(birthdate, '%Y-%m-%d')
                birth_date = SGT.localize(birth_date)
                age = (get_sgt_now() - birth_date).days / 365.25
                if age < 13:
                    errors.append("Must be at least 13 years old")
                if age > 100:
                    errors.append("Age cannot exceed 100 years")
            except ValueError:
                errors.append("Invalid birthdate format")
        if interests is not None and len(interests) == 0:
            errors.append("Please select at least one interest")
        return errors

    def get_by_id(self, user_id):
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            return self._user_to_dict(user)
        return None
    
    def get_by_username(self, username):
        user = self.session.query(User).filter_by(username=username).first()
        if user:
            return self._user_to_dict(user)
        return None
    
    def get_by_email(self, email):
        user = self.session.query(User).filter_by(email=email).first()
        if user:
            return self._user_to_dict(user)
        return None
    
    def verify_password(self, email, password):
        user = self.session.query(User).filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            return self._user_to_dict(user)
        return None
    
    def calculate_age(self, birthdate):
        today = get_sgt_now()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    
    def follow(self, follower_id, following_id):
        existing = self.session.query(Follow).filter_by(follower_id=follower_id, followed_id=following_id).first()
        if not existing and follower_id != following_id:
            follow = Follow(follower_id=follower_id, followed_id=following_id)
            self.session.add(follow)
            self.session.commit()
            return True
        return False

    def unfollow(self, follower_id, following_id):
        follow = self.session.query(Follow).filter_by(follower_id=follower_id, followed_id=following_id).first()
        if follow:
            self.session.delete(follow)
            self.session.commit()
            return True
        return False

    def is_following(self, follower_id, following_id):
        return self.session.query(Follow).filter_by(follower_id=follower_id, followed_id=following_id).first() is not None

    def get_followers(self, user_id):
        followers = self.session.query(User).join(Follow, User.id == Follow.follower_id).filter(
            Follow.followed_id == user_id
        ).all()
        return [self._user_to_dict(f) for f in followers]
    
    def get_following(self, user_id):
        following = self.session.query(User).join(Follow, User.id == Follow.followed_id).filter(
            Follow.follower_id == user_id
        ).all()
        return [self._user_to_dict(f) for f in following]
    
    def _user_to_dict(self, user):
        profile_pic = user.profile_picture_url or user.profile_picture
        if not profile_pic or profile_pic.strip() == '':
            profile_pic = 'img/default_avatar.png'
        # Prefix relative paths so they resolve correctly as URLs
        if profile_pic and not profile_pic.startswith(('/', 'http', 'data:')):
            profile_pic = f'/static/{profile_pic}'
        
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'password_hash': user.password_hash,
            'birthdate': user.date_of_birth,
            'profile_picture': profile_pic,
            'interests': [h.name for h in user.hobbies],
            'bio': user.bio,
            'is_admin': user.is_admin,
            'created_at': user.created_at,
            'updated_at': user.updated_at
        }

class PostService:
    def __init__(self, session):
        self.session = session
    
    def validate_post(self, content, image_url=None, hashtags=None):
        errors = []
        if not content or len(content.strip()) == 0:
            errors.append("Post content cannot be empty")
        if len(content) > 280:
            errors.append("Post content cannot exceed 280 characters")
        if hashtags:
            if len(hashtags) > 3:
                errors.append("Maximum 3 hashtags allowed per post")
            for tag in hashtags:
                if not tag.startswith('#'):
                    errors.append(f"Hashtag '{tag}' must start with #")
                if len(tag) < 2:
                    errors.append(f"Hashtag '{tag}' is too short")
                if len(tag) > 30:
                    errors.append(f"Hashtag '{tag}' is too long (max 30 characters)")
                if ' ' in tag:
                    errors.append(f"Hashtag '{tag}' cannot contain spaces")
        return errors
    
    def create(self, user_id, content, forum_id=None, image_url=None, 
               is_repost=False, original_post_id=None, quote_content=None, hashtags=None):
        hashtags_json = json.dumps(hashtags) if hashtags else json.dumps([])
        post = Post(
            user_id=user_id,
            forum_id=forum_id,
            content=content,
            image_url=image_url,
            hashtags=hashtags_json,
            is_repost=is_repost,
            original_post_id=original_post_id,
            quote_content=quote_content
        )
        self.session.add(post)
        if is_repost and original_post_id:
            original = self.session.query(Post).filter_by(id=original_post_id).first()
            if original:
                original.reposts_count += 1
        self.session.commit()
        return post.id
    
    def get_by_id(self, post_id):
        post = self.session.query(Post).filter_by(id=post_id).first()
        if post:
            return self._post_to_dict(post)
        return None
    
    def get_by_user(self, user_id, limit=50):
        posts = self.session.query(Post).filter_by(user_id=user_id).order_by(
            desc(Post.created_at)
        ).limit(limit).all()
        return [self._post_to_dict(p) for p in posts]
    
    def get_by_forum(self, forum_id, limit=50):
        posts = self.session.query(Post).filter_by(forum_id=forum_id).order_by(
            desc(Post.created_at)
        ).limit(limit).all()
        return [self._post_to_dict(p) for p in posts]
    
    def get_by_hashtag(self, hashtag, filter_by='recent', limit=50):
        query = self.session.query(Post).filter(
            Post.hashtags.like(f'%{hashtag}%')
        )
        if filter_by == 'liked':
            posts = query.order_by(desc(Post.likes_count), desc(Post.created_at)).limit(limit).all()
        elif filter_by == 'activity':
            activity_score = (Post.likes_count + Post.comments_count + Post.reposts_count)
            posts = query.order_by(desc(activity_score), desc(Post.created_at)).limit(limit).all()
        else:
            posts = query.order_by(desc(Post.created_at)).limit(limit).all()
        return [self._post_to_dict(p) for p in posts]
    
    def delete(self, post_id):
        post = self.session.query(Post).filter_by(id=post_id).first()
        if post:
            if post.is_repost and post.original_post_id:
                original = self.session.query(Post).filter_by(id=post.original_post_id).first()
                if original and original.reposts_count > 0:
                    original.reposts_count -= 1
            self.session.delete(post)
            self.session.commit()
            return True
        return False
    
    def like(self, post_id, user_id):
        existing = self.session.query(Like).filter_by(post_id=post_id, user_id=user_id).first()
        if not existing:
            like = Like(post_id=post_id, user_id=user_id)
            self.session.add(like)
            post = self.session.query(Post).filter_by(id=post_id).first()
            if post:
                post.likes_count += 1
            self.session.commit()
            return True
        return False
    
    def unlike(self, post_id, user_id):
        like = self.session.query(Like).filter_by(post_id=post_id, user_id=user_id).first()
        if like:
            self.session.delete(like)
            post = self.session.query(Post).filter_by(id=post_id).first()
            if post and post.likes_count > 0:
                post.likes_count -= 1
            self.session.commit()
            return True
        return False
    
    def is_liked_by(self, post_id, user_id):
        return self.session.query(Like).filter_by(post_id=post_id, user_id=user_id).first() is not None
    
    def _post_to_dict(self, post):
        user = post.user
        forum = post.forum
        profile_pic = user.profile_picture_url or user.profile_picture
        
        original_post_data = None
        if post.is_repost and post.original_post_id:
            original_post = self.session.query(Post).filter_by(id=post.original_post_id).first()
            if original_post:
                original_user = original_post.user
                original_profile_pic = original_user.profile_picture_url or original_user.profile_picture
                
                user_service = UserService(self.session)
                original_age = user_service.calculate_age(original_user.date_of_birth)
                original_post_data = {
                    'id': original_post.id,
                    'user_id': original_post.user_id,
                    'username': original_user.username,
                    'profile_picture': original_profile_pic,
                    'age': original_age,
                    'age_group': original_user.age_group,
                    'content': original_post.content,
                    'image_url': original_post.image_url,
                    'created_at': original_post.created_at
                }
        return {
            'id': post.id,
            'user_id': post.user_id,
            'forum_id': post.forum_id,
            'content': post.content,
            'image_url': post.image_url,
            'hashtags': json.loads(post.hashtags) if post.hashtags else [],
            'is_repost': post.is_repost,
            'original_post_id': post.original_post_id,
            'original_post': original_post_data,
            'quote_content': post.quote_content,
            'likes_count': post.likes_count,
            'reposts_count': post.reposts_count,
            'comments_count': post.comments_count,
            'created_at': post.created_at,
            'updated_at': post.updated_at,
            'username': user.username,
            'profile_picture': profile_pic,
            'birthdate': user.date_of_birth,
            'age_group': user.age_group,
            'forum_name': forum.name if forum else None,
            'forum_banner': forum.banner if forum else None
        }

class ForumService:
    def __init__(self, session):
        self.session = session
    
    def validate_creation(self, user_id, name, description):
        errors = []
        if not name or len(name) < 3 or len(name) > 100:
            errors.append("Forum name must be between 3 and 100 characters")
        if not description or len(description) < 10:
            errors.append("Description must be at least 10 characters")
        if self.session.query(Forum).filter_by(name=name).first():
            errors.append("Forum name already exists")
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            created_at = user.created_at
            if created_at.tzinfo is None:
                created_at = SGT.localize(created_at)
            account_age = get_sgt_now() - created_at
            if account_age.seconds < 7: 
                errors.append("Account must be at least 7 days old to create a forum")
        forum_count = self.session.query(Forum).filter_by(creator_id=user_id).count()
        if forum_count >= 5:
            errors.append("Maximum 5 forums per account")
        return errors
    
    def create(self, name, description, creator_id, is_private=False, interest_tags=None, rules=None, banner=None, moderator_ids=None):
        interest_tags_json = json.dumps(interest_tags) if interest_tags else json.dumps([])
        forum = Forum(
            name=name,
            description=description,
            rules=rules,
            banner=banner,
            creator_id=creator_id,
            is_private=is_private,
            interest_tags=interest_tags_json
        )
        self.session.add(forum)
        self.session.flush()
        creator = self.session.query(User).filter_by(id=creator_id).first()
        if creator:
            forum.members.append(creator)
            forum.moderators.append(creator)
        if moderator_ids:
            for mod_id in moderator_ids:
                moderator = self.session.query(User).filter_by(id=mod_id).first()
                if moderator and moderator not in forum.moderators:
                    forum.moderators.append(moderator)
                    if moderator not in forum.members:
                        forum.members.append(moderator)
        self.session.commit()
        return forum.id
    
    def get_by_id(self, forum_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        if forum:
            return self._forum_to_dict(forum)
        return None
    
    def is_member(self, forum_id, user_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        user = self.session.query(User).filter_by(id=user_id).first()
        return user in forum.members if (forum and user) else False
    
    def is_moderator(self, forum_id, user_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        user = self.session.query(User).filter_by(id=user_id).first()
        return user in forum.moderators if (forum and user) else False
    
    def join(self, forum_id, user_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        user = self.session.query(User).filter_by(id=user_id).first()
        if forum and user and user not in forum.members:
            forum.members.append(user)
            self.session.commit()
            return True
        return False
    
    def leave(self, forum_id, user_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        user = self.session.query(User).filter_by(id=user_id).first()
        if forum and user and user in forum.members:
            forum.members.remove(user)
            self.session.commit()
            return True
        return False
    
    def get_moderators(self, forum_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        if forum:
            moderators = []
            for mod in forum.moderators:
                mod_dict = {
                    'id': mod.id,
                    'username': mod.username,
                    'profile_picture': mod.profile_picture if mod.profile_picture and mod.profile_picture.strip() else 'img/default_avatar.png'
                }
                moderators.append(mod_dict)
            return moderators
        return []

    def get_joined_forums(self, user_id):
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            return [self._forum_to_dict(f) for f in user.joined_forums]
        return []
    
    def get_recommended_forums(self, user_id, interests):
        if not interests:
            return []
        user = self.session.query(User).filter_by(id=user_id).first()
        joined_ids = [f.id for f in user.joined_forums] if user else []
        forums = self.session.query(Forum).filter(
            Forum.is_private == False,
            ~Forum.id.in_(joined_ids) if joined_ids else True
        ).limit(10).all()
        recommended = []
        for forum in forums:
            tags = json.loads(forum.interest_tags) if forum.interest_tags else []
            if any(interest in tags for interest in interests):
                recommended.append(self._forum_to_dict(forum))
        return recommended[:10]
    
    def search_forums(self, query_text, filter_by='activity', interest_tag=None):
        q = self.session.query(Forum).filter(Forum.is_private == False)
        if query_text:
            q = q.filter(Forum.name.like(f'%{query_text}%'))
        if interest_tag:
            q = q.filter(Forum.interest_tags.like(f'%{interest_tag}%'))
        if filter_by == 'popularity':
            forums = q.all()
            forums.sort(key=lambda f: len(f.members), reverse=True)
        elif filter_by == 'newest':
            forums = q.order_by(desc(Forum.created_at)).all()
        else:
            forums = q.order_by(desc(Forum.updated_at)).all()
        return [self._forum_to_dict(f) for f in forums[:50]]
    
    def update(self, forum_id, name, description, rules, is_private, interest_tags, banner):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        if forum:
            forum.name = name
            forum.description = description
            forum.rules = rules
            forum.is_private = is_private
            forum.interest_tags = json.dumps(interest_tags) if interest_tags else json.dumps([])
            forum.banner = banner
            self.session.commit()
            return True
        return False

    def update_moderators(self, forum_id, creator_id, moderator_ids):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        if forum:
            # Clear existing moderators except creator
            creator = self.session.query(User).filter_by(id=creator_id).first()
            forum.moderators = [creator] if creator else []
            
            # Add new moderators
            for mod_id in moderator_ids:
                if mod_id != creator_id:
                    moderator = self.session.query(User).filter_by(id=mod_id).first()
                    if moderator and moderator not in forum.moderators:
                        forum.moderators.append(moderator)
                        if moderator not in forum.members:
                            forum.members.append(moderator)
            
            self.session.commit()
            return True
        return False

    def delete(self, forum_id):
        forum = self.session.query(Forum).filter_by(id=forum_id).first()
        if forum:
            self.session.delete(forum)
            self.session.commit()
            return True
        return False

    def validate_forum(self, name, description, user_id, editing=False, current_forum_id=None):
        errors = []
        if not name or len(name) < 3:
            errors.append("Forum name must be at least 3 characters")
        if not description or len(description) < 10:
            errors.append("Description must be at least 10 characters")
        
        # Check for duplicate name only if name changed
        existing = self.session.query(Forum).filter_by(name=name).first()
        if existing and (not editing or existing.id != current_forum_id):
            errors.append("Forum name already exists")
        
        # Only check account age and forum count when creating, not editing
        if not editing:
            user = self.session.query(User).filter_by(id=user_id).first()
            if user:
                created_at = user.created_at
                if created_at.tzinfo is None:
                    created_at = SGT.localize(created_at)
                account_age = get_sgt_now() - created_at
                if account_age.seconds < 7: 
                    errors.append("Account must be at least 7 days old to create a forum")
            
            forum_count = self.session.query(Forum).filter_by(creator_id=user_id).count()
            if forum_count >= 5:
                errors.append("Maximum 5 forums per account")
        
        return errors
    
    def _forum_to_dict(self, forum):
        creator_profile_pic = forum.creator.profile_picture
        if not creator_profile_pic or creator_profile_pic.strip() == '':
            creator_profile_pic = 'img/default_avatar.png'

        return {
            'id': forum.id,
            'name': forum.name,
            'description': forum.description,
            'rules': forum.rules,
            'banner': forum.banner,
            'creator_id': forum.creator_id,
            'is_private': forum.is_private,
            'interest_tags': forum.interest_tags,
            'created_at': forum.created_at,
            'updated_at': forum.updated_at,
            'creator_username': forum.creator.username,
            'creator_profile_picture': creator_profile_pic,
            'member_count': len(forum.members)
        }

class CommentService:
    def __init__(self, session):
        self.session = session
    
    def validate_comment(self, content):
        errors = []
        if not content or len(content.strip()) == 0:
            errors.append("Comment cannot be empty")
        if len(content) > 280:
            errors.append("Comment cannot exceed 280 characters")
        return errors
    
    def create(self, post_id, user_id, content):
        comment = Comment(post_id=post_id, user_id=user_id, content=content)
        self.session.add(comment)
        post = self.session.query(Post).filter_by(id=post_id).first()
        if post:
            post.comments_count += 1
        self.session.commit()
        return comment.id
    
    def get_by_post(self, post_id):
        comments = self.session.query(Comment).filter_by(post_id=post_id).order_by(
            Comment.created_at
        ).all()
        return [self._comment_to_dict(c) for c in comments]
    
    def _comment_to_dict(self, comment):
        user = comment.user
        profile_pic = user.profile_picture_url or user.profile_picture
        
        return {
            'id': comment.id,
            'post_id': comment.post_id,
            'user_id': comment.user_id,
            'content': comment.content,
            'created_at': comment.created_at,
            'username': user.username,
            'profile_picture': profile_pic,
            'birthdate': user.date_of_birth
        }

class NotificationService:
    def __init__(self, session):
        self.session = session
    
    def create(self, user_id, notification_type, content, related_id=None):
        notif = Notification(
            user_id=user_id,
            type=notification_type,
            message=content, # Mapped to message
            related_id=related_id
        )
        self.session.add(notif)
        self.session.commit()
        return notif.id
    
    def get_by_user(self, user_id, limit=50):
        notifs = self.session.query(Notification).filter_by(user_id=user_id).order_by(
            desc(Notification.created_at)
        ).limit(limit).all()
        return [self._notif_to_dict(n) for n in notifs]
    
    def mark_as_read(self, notification_id):
        notif = self.session.query(Notification).filter_by(id=notification_id).first()
        if notif:
            notif.read_at = get_sgt_now() # Mapped to read_at
            self.session.commit()
            return True
        return False
    
    def mark_all_as_read(self, user_id):
        self.session.query(Notification).filter_by(user_id=user_id).update({'read_at': get_sgt_now()})
        self.session.commit()
        return True

    def clear_all(self, user_id):
        self.session.query(Notification).filter_by(user_id=user_id).delete()
        self.session.commit()
        return True
    
    def _notif_to_dict(self, notif):
        return {
            'id': notif.id,
            'user_id': notif.user_id,
            'type': notif.type,
            'content': notif.message, # Mapped back to content
            'related_id': notif.related_id,
            'is_read': notif.read_at is not None, # Check if read
            'created_at': notif.created_at
        }

class BanService:
    def __init__(self, session):
        self.session = session
    
    def create(self, user_id, forum_id, moderator_id, reason):
        ban = Ban(
            user_id=user_id,
            forum_id=forum_id,
            moderator_id=moderator_id,
            reason=reason
        )
        self.session.add(ban)
        self.session.commit()
        return ban.id
    
    def is_banned(self, user_id, forum_id):
        return self.session.query(Ban).filter_by(
            user_id=user_id, forum_id=forum_id
        ).first() is not None
