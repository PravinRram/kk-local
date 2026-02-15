"""
Database seeding script for Kampong Konek (Merged)
This script populates the database using the new SQLAlchemy models and schema.
"""

import json
import sys
import os
from datetime import datetime

# Check context and import accordingly
if os.path.exists(os.path.join(os.getcwd(), 'models.py')) and os.path.exists(os.path.join(os.getcwd(), '__init__.py')):
    # Running from merged directory
    from models import db, User, Forum, Post, Comment, Like, Follow, Hobby, Notification
    from __init__ import create_app
    from sqlalchemy import insert
else:
    # Fallback/Error if not in merged directory
    print("Error: Please run this script from the 'merged' directory.")
    print("Usage: cd merged && .venv\\Scripts\\python seeding.py")
    sys.exit(1)

def seed_database():
    app = create_app()
    with app.app_context():
        print(f"Seeding database at: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        print("Seeding data...")
        
        # --- Pre-populate Hobbies ---
        hobbies_list = ["Technology", "Art", "Gaming", "Entertainment", "Identity", "Music", "Education", "Science", "Travel", "Books", "Fashion", "Business", "Politics", "Health", "Sports", "Cooking", "Fitness"]
        for name in hobbies_list:
            if not Hobby.query.filter_by(name=name).first():
                db.session.add(Hobby(name=name))
        db.session.commit()
        
        # --- Users ---
        # Data format: (id, username, email, password_hash, birthdate, profile_picture, interests, bio, is_admin, created_at, updated_at)
        users_data = [
            (1, "test", "test@gmail.com", "scrypt:32768:8:1$pYRHCRjhlig27LMA$0a2c943f64c26111b42bd0b96b529fc7afee59166dd17a7cf7e0fe70134757bfdd98492005eb2413ecba906310a4c6c27d82f4fc5c4d1368116cc81f2f938e9b", "2008-03-02", "https://99designs-blog.imgix.net/blog/wp-content/uploads/2018/12/Gradient_builder_2.jpg", '["Technology", "Art", "Gaming", "Entertainment", "Identity", "Music", "Education", "Science"]', "this is a test", 0, "2026-01-25 03:56:34.456909", "2026-01-25 03:56:34.456920"),
            (2, "test2", "test2@gmail.com", "scrypt:32768:8:1$CDsK0n0tRtJOezaE$0b7f35e88aa769ccc83f0f01bf35415f6f717120f91b97d728e014cbbef96fb40490fe7d3e8765d063c8371456ca25fe417ca7fae4ec67dcba206b0056fee13b", "2010-03-02", "/static/uploads/profiles/81c306a3b28d45948555ec90110fe585.png", '["Technology", "Gaming", "Travel", "Entertainment", "Music", "Books", "Fashion", "Education", "Business", "Politics", "Health"]', "hi", 0, "2026-01-25 12:41:20.932174", "2026-01-29 08:26:41.217836"),
            (3, "test3", "test3@gmail.com", "scrypt:32768:8:1$mJQ0hWelhfxBvJDT$983483fc28b9b711b4229c5ab21de7fbf4d162364523aa364456e727c61d3134e8e64676348cb3a9ccb77685debfb7d8f44fc7e3a6dd7bcdc6efcca3c1954223", "2001-02-02", "/static/images/default-avatar.png", '["Technology"]', "hasiaiciascioac", 0, "2026-01-25 14:07:28.927117", "2026-01-29 02:37:41.905731"),
            (4, "admin", "admin@gmail.com", "scrypt:32768:8:1$eVWMWNqZyaO9NTJ8$9733f95805eb4cb384fa0b3f7894d67538ba4df57d6bb8b69a38125a8013e2a0cbc5f6a8a796d5b53b43a21bb730466773ab8001cd5ad5e2de32dbaec0efe753", "2009-01-29", "/static/images/default-avatar.png", '["Technology", "Sports", "Art", "Gaming", "Cooking", "Travel", "Entertainment", "Identity", "Music", "Books", "Fitness", "Fashion", "Education", "Business", "Science", "Politics", "Health"]', "", 1, "2026-01-29 13:38:54.492184", "2026-01-29 14:10:52.321195")
        ]

        for u_data in users_data:
            uid, username, email, pwd_hash, dob_str, pfp, interests_json, bio, is_admin, created_at_str, updated_at_str = u_data
            
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
            updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            user = User(
                id=uid,
                username=username,
                email=email,
                password_hash=pwd_hash,
                date_of_birth=dob,
                profile_picture_url=pfp, 
                bio=bio,
                is_admin=bool(is_admin),
                created_at=created_at,
                updated_at=updated_at,
                display_name=username,
                privacy="public"
            )
            
            db.session.add(user) # Add to session before relationship operations
            
            try:
                interest_names = json.loads(interests_json)
                for name in interest_names:
                    hobby = Hobby.query.filter_by(name=name).first()
                    if hobby:
                        user.hobbies.append(hobby)
            except:
                pass
        
        db.session.commit()
        print(f"✓ Inserted {len(users_data)} users")

        # --- Follows ---
        follows_data = [
            (1, 1, 2, "2026-01-25 12:56:03.654368"),
            (2, 2, 1, "2026-01-25 12:59:38.869201"),
            (3, 3, 1, "2026-01-25 14:51:34.306516"),
            (4, 3, 2, "2026-01-25 14:51:38.545826"),
            (5, 2, 3, "2026-01-25 15:01:37.439831")
        ]
        
        for f_data in follows_data:
            fid, follower_id, following_id, created_at_str = f_data
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            follow = Follow(
                id=fid,
                follower_id=follower_id,
                followed_id=following_id,
                created_at=created_at
            )
            db.session.add(follow)
        
        db.session.commit()
        print(f"✓ Inserted {len(follows_data)} follows")

        # --- Forums ---
        forums_data = [
            (1, "test", "testtestest", 1, 0, '["Technology", "Identity", "Music", "Business"]', "2026-01-25 04:01:19.816909", "2026-01-25 04:01:19.816915", None, None),
            (2, "test2", "testtesttest", 2, 0, '["Technology", "Gaming", "Entertainment"]', "2026-01-29 11:51:26.941763", "2026-01-29 11:51:26.941792", "1. Be respectful & civil\r\n2. Keep posts on topic\r\n3. No spam / self-promotion", "/static/uploads/posts/fa105e9fa4864caa821d6acc993b2514.png"),
            (3, "coding", "tstststvgvvvvvvvvvvvvvvvvvvvv", 3, 0, '["Technology", "Gaming", "Entertainment", "Books"]', "2026-01-29 14:28:11.236590", "2026-01-29 14:28:11.236612", "1. Be respectful & civil\r\n2. Keep posts on topic\r\n3. No spam / self-promotion", "/static/uploads/posts/33c4c4f5d3a848af946947cac05b8ea8.png")
        ]
        
        for forum_data in forums_data:
            fid, name, desc, creator_id, is_private, tags, created_at_str, updated_at_str, rules, banner = forum_data
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
            updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            forum = Forum(
                id=fid,
                name=name,
                description=desc,
                creator_id=creator_id,
                is_private=bool(is_private),
                interest_tags=tags,
                created_at=created_at,
                updated_at=updated_at,
                rules=rules,
                banner=banner
            )
            db.session.add(forum)
        
        db.session.commit()
        print(f"✓ Inserted {len(forums_data)} forums")

        # --- Forum Members ---
        forum_members_data = [
            (1, 1, 1, "2026-01-25 04:01:19.825233"),
            (2, 1, 2, "2026-01-26 00:59:56.824451"),
            (4, 2, 1, "2026-01-29 11:51:26.936414"),
            (5, 2, 2, "2026-01-29 14:28:11.230641"),
            (6, 3, 3, "2026-01-29 14:28:11.230641")
        ]
        
        for fm_data in forum_members_data:
            _, fid, uid, joined_at_str = fm_data
            joined_at = datetime.strptime(joined_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            stmt = insert(db.metadata.tables['forum_members']).values(
                forum_id=fid,
                user_id=uid,
                joined_at=joined_at
            )
            db.session.execute(stmt)

        # --- Forum Moderators ---
        forum_moderators_data = [
            (1, 1, 1, "2026-01-25 04:01:19.829340"),
            (2, 2, 2, "2026-01-29 11:51:26.937202"),
            (3, 2, 1, "2026-01-29 11:51:26.937202"),
            (4, 3, 3, "2026-01-29 14:28:11.231395")
        ]
        
        for fmod_data in forum_moderators_data:
            _, fid, uid, added_at_str = fmod_data
            added_at = datetime.strptime(added_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            stmt = insert(db.metadata.tables['forum_moderators']).values(
                forum_id=fid,
                user_id=uid,
                added_at=added_at
            )
            db.session.execute(stmt)
            
        db.session.commit()
        print(f"✓ Inserted members and moderators")

        # --- Posts ---
        posts_data = [
            (1, 1, None, "solo test", "https://plus.unsplash.com/premium_photo-1672201106204-58e9af7a2888?fm=jpg", 0, None, None, 0, 0, 0, "2026-01-25 04:07:06.505223", "2026-01-25 04:07:06.505228", None),
            (2, 1, None, "solo test", "https://plus.unsplash.com/premium_photo-1672201106204-58e9af7a2888?fm=jpg", 0, None, None, 0, 0, 0, "2026-01-25 04:07:12.608082", "2026-01-25 04:07:12.608087", None),
            (3, 1, 1, "forum test", "https://plus.unsplash.com/premium_photo-1672201106204-58e9af7a2888?fm=jpg", 0, None, None, 0, 1, 0, "2026-01-25 04:07:52.904429", "2026-01-28 18:15:58.211509", None),
            (4, 1, None, "testtestestststts", "", 0, None, None, 0, 0, 0, "2026-01-25 12:37:34.976861", "2026-01-28 21:49:12.852279", None),
            (5, 1, None, "this is a test", "", 0, None, None, 1, 0, 0, "2026-01-25 12:40:55.310514", "2026-01-28 19:00:23.403735", None),
            (6, 1, None, "testststststststst", "", 0, None, None, 0, 0, 0, "2026-01-25 12:42:02.020899", "2026-01-25 12:42:02.020903", None),
            (7, 2, None, "hi", "", 0, None, None, 3, 0, 0, "2026-01-25 12:59:55.420499", "2026-01-29 14:28:11.238565", None),
            (8, 1, 1, "tsessesfgkkkjkkkkk", "", 0, None, None, 2, 0, 0, "2026-01-25 13:35:58.236472", "2026-01-28 22:23:11.557908", None),
            (9, 3, None, "huh", None, 1, 3, "huh", 2, 1, 0, "2026-01-28 18:15:58.200359", "2026-01-29 12:58:27.109206", None),
            (10, 1, None, "as", "", 0, None, None, 0, 0, 0, "2026-01-28 20:24:21.016267", "2026-01-28 22:22:43.614957", '["#w"]'),
            (11, 1, 1, "hashtag test", "", 0, None, None, 1, 0, 0, "2026-01-28 20:33:45.398056", "2026-01-28 21:49:05.233386", '["#test"]'),
            (12, 1, None, "hhhdhdhh", "", 0, None, None, 1, 0, 0, "2026-01-28 21:06:57.544780", "2026-01-28 22:22:40.518812", '["#1", "#2", "#3"]'),
            (13, 1, None, "Ssaa", "", 0, None, None, 1, 0, 0, "2026-01-28 22:38:30.603850", "2026-01-28 22:38:33.598821", '["#hi"]'),
            (14, 1, None, "lol", "", 0, None, None, 0, 1, 0, "2026-01-29 00:06:29.483737", "2026-01-29 02:58:26.563116", '["#hi"]'),
            (15, 2, None, "test", "/static/uploads/posts/399d23fc9a53446a84bd1eb110639506.png", 0, None, None, 0, 0, 0, "2026-01-29 03:20:47.336384", "2026-01-29 03:20:47.336427", '["#hi"]'),
            (16, 1, None, "test", "", 0, None, None, 0, 0, 0, "2026-01-29 03:20:47.336384", "2026-01-29 03:20:47.336427", '["#test"]'),
            (19, 2, None, "", None, 1, 9, None, 0, 0, 0, "2026-01-29 12:58:27.109177", "2026-01-29 12:58:27.109203", "[]"),
            (20, 3, None, "hhshshhshssh", "/static/uploads/posts/28ed084de87848e384bb9406f2d6a46b.png", 0, None, None, 0, 0, 0, "2026-01-29 14:28:11.238544", "2026-01-29 14:28:11.238564", '["#test", "#j"]'),
            (21, 3, None, "hi", "", 0, None, None, 0, 0, 0, "2026-01-29 14:28:11.238544", "2026-01-29 14:28:11.238564", "[]"),
            (22, 3, 3, "hi", "", 0, None, None, 1, 0, 0, "2026-01-29 14:28:11.238544", "2026-02-09 21:24:50.534413", "[]")
        ]
        
        for p_data in posts_data:
            pid, uid, fid, content, img_url, is_repost, orig_post_id, quote, likes, reposts, comments, created_at_str, updated_at_str, hashtags = p_data
            
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
            updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            post = Post(
                id=pid,
                user_id=uid,
                forum_id=fid,
                content=content,
                image_url=img_url,
                is_repost=bool(is_repost),
                original_post_id=orig_post_id,
                quote_content=quote,
                likes_count=likes,
                reposts_count=reposts,
                comments_count=comments,
                created_at=created_at,
                updated_at=updated_at,
                hashtags=hashtags
            )
            db.session.add(post)
            
        db.session.commit()
        print(f"✓ Inserted {len(posts_data)} posts")

        # --- Likes ---
        likes_data = [
            (2, 8, 3, "2026-01-28 17:59:59.377798"),
            (3, 5, 2, "2026-01-28 19:00:23.399417"),
            (4, 7, 2, "2026-01-28 19:06:42.945637"),
            (5, 9, 2, "2026-01-28 19:09:51.519003"),
            (6, 7, 1, "2026-01-28 21:48:44.398044"),
            (8, 11, 1, "2026-01-28 21:49:05.226987"),
            (9, 12, 1, "2026-01-28 22:22:40.512702"),
            (10, 8, 1, "2026-01-28 22:23:11.553748"),
            (11, 9, 1, "2026-01-28 22:23:27.748014"),
            (12, 13, 1, "2026-01-28 22:38:33.593576"),
            (13, 7, 3, "2026-01-29 14:28:11.241170"),
            (14, 22, 1, "2026-02-09 21:24:50.537643")
        ]
        
        for l_data in likes_data:
            lid, pid, uid, created_at_str = l_data
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S.%f")
            
            like = Like(
                id=lid,
                post_id=pid,
                user_id=uid,
                created_at=created_at
            )
            db.session.add(like)
            
        db.session.commit()
        print(f"✓ Inserted {len(likes_data)} likes")
        
        print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    seed_database()
