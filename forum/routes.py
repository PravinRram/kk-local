import json

from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app
)
from sqlalchemy import or_

from models import db, User, Post, Follow
from services import UserService, PostService, ForumService, CommentService, NotificationService, BanService
from decorators import login_required
from utils import process_post_image, process_profile_picture, process_forum_image, allowed_file
from moderation import moderate_content
from config import Config
from extensions import socketio
from . import forum_bp

# --- Forum Routes (Feed, Posts, Forums) ---

@forum_bp.route('/feed')
@login_required
def feed():
    sess = db.session
    post_service = PostService(sess)
    user_service = UserService(sess)
    
    following = sess.query(Follow).filter_by(follower_id=session['user_id']).all()
    following_ids = {f.followed_id for f in following}
    
    user = g.current_user
    forum_ids = {f.id for f in user.joined_forums}
    
    user_ids = following_ids | {session['user_id']}
    
    posts_query = sess.query(Post).filter(
        or_(
            Post.user_id.in_(user_ids),
            Post.forum_id.in_(forum_ids) if forum_ids else False
        )
    ).order_by(Post.created_at.desc()).limit(50).all()
    
    posts = [post_service._post_to_dict(p) for p in posts_query]
    
    for post in posts:
            # Calculate age
        post_user = User.query.get(post['user_id'])
        if post_user:
                post['age'] = user_service.calculate_age(post_user.date_of_birth)
        else:
                post['age'] = 0
        post['is_liked'] = post_service.is_liked_by(post['id'], session['user_id'])

    return render_template('feed.html', posts=posts)

@forum_bp.route('/post/create', methods=['POST'])
@login_required
def create_post():
    sess = db.session
    post_service = PostService(sess)
    forum_service = ForumService(sess)
    ban_service = BanService(sess)
    
    content = request.form.get('content', '').strip()
    forum_id = request.form.get('forum_id')
    hashtags_raw = request.form.get('hashtags', '').strip()
    
    # 1. Try to get image from hidden input (pre-uploaded)
    image_url = request.form.get('image_url', '').strip()

    # 2. If not pre-uploaded, check if file is in request (fallback)
    if not image_url and 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            image_url = process_post_image(file)

    print(f"DEBUG: create_post called. Content: '{content}', Image URL: '{image_url}', Forum ID: {forum_id}")

    text_fields = {
        'Post Content': content,
        'Hashtags': hashtags_raw
    }
    image_path = image_url.lstrip('/') if image_url else None
    moderation_result = moderate_content(text_fields=text_fields, image_path=image_path)
    
    if moderation_result['flagged']:
        return render_template('moderation_error.html', 
                            error_message=moderation_result['message'],
                            return_url=request.referrer or url_for('forum.feed'))
    
    hashtags = []
    if hashtags_raw:
        hashtags = [tag.strip() for tag in hashtags_raw.split(',') if tag.strip()]

    errors = post_service.validate_post(content, image_url, hashtags)
    
    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect(request.referrer or url_for('forum.feed'))
    
    if forum_id:
        forum_id = int(forum_id)
        if not forum_service.is_member(forum_id, session['user_id']):
            flash('You must be a member to post in this forum', 'error')
            return redirect(request.referrer or url_for('forum.feed'))
        
        if ban_service.is_banned(session['user_id'], forum_id):
            flash('You are banned from this forum', 'error')
            return redirect(request.referrer or url_for('forum.feed'))
    
    post_id = post_service.create(session['user_id'], content, forum_id, image_url, hashtags=hashtags)
    
    socketio.emit('new_post', {'post_id': post_id}, namespace='/')
    flash('Post created successfully', 'success')
    return redirect(request.referrer or url_for('forum.feed'))

@forum_bp.route('/post/<int:post_id>')
@login_required
def post_detail(post_id):
    sess = db.session
    user_service = UserService(sess)
    post_service = PostService(sess)
    comment_service = CommentService(sess)
    
    post = post_service.get_by_id(post_id)
    
    if not post:
        flash('Post not found', 'error')
        return redirect(url_for('forum.feed'))
    
    post_user = User.query.get(post['user_id'])
    post['age'] = user_service.calculate_age(post_user.date_of_birth) if post_user else 0
    post['is_liked'] = post_service.is_liked_by(post_id, session['user_id'])
    
    comments = comment_service.get_by_post(post_id)
    for comment in comments:
        comment_user = User.query.get(comment['user_id'])
        comment['age'] = user_service.calculate_age(comment_user.date_of_birth) if comment_user else 0
    
    return render_template('post_detail.html', post=post, comments=comments)

@forum_bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    sess = db.session
    post_service = PostService(sess)
    
    if post_service.is_liked_by(post_id, session['user_id']):
        post_service.unlike(post_id, session['user_id'])
    else:
        post_service.like(post_id, session['user_id'])
    
    return jsonify({'success': True})

@forum_bp.route('/post/<int:post_id>/repost', methods=['POST'])
@login_required
def repost(post_id):
    sess = db.session
    post_service = PostService(sess)
    
    quote_content = request.form.get('quote_content', '').strip()
    is_quote = len(quote_content) > 0
    
    new_post_id = post_service.create(
        session['user_id'],
        quote_content if is_quote else '',
        None,
        None,
        True,
        post_id,
        quote_content if is_quote else None
    )
    
    flash('Post reposted successfully', 'success')
    return redirect(url_for('forum.feed'))

@forum_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    sess = db.session
    comment_service = CommentService(sess)
    
    content = request.form.get('content', '').strip()
    
    errors = comment_service.validate_comment(content)
    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('forum.post_detail', post_id=post_id))
    
    comment_service.create(post_id, session['user_id'], content)
    flash('Comment added successfully', 'success')
    return redirect(url_for('forum.post_detail', post_id=post_id))

@forum_bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    sess = db.session
    post_service = PostService(sess)
    forum_service = ForumService(sess)
    
    post = post_service.get_by_id(post_id)
    
    if not post:
        flash('Post not found', 'error')
        return redirect(url_for('forum.feed'))
    
    can_delete = (post['user_id'] == session['user_id'] or
                    session.get('is_admin') or
                    (post['forum_id'] and forum_service.is_moderator(post['forum_id'], session['user_id'])))
    
    if not can_delete:
        flash('You do not have permission to delete this post', 'error')
        return redirect(request.referrer or url_for('forum.feed'))
    
    post_service.delete(post_id)
    flash('Post deleted successfully', 'success')
    return redirect(request.referrer or url_for('forum.feed'))

@forum_bp.route('/forums')
@login_required
def forums():
    sess = db.session
    forum_service = ForumService(sess)
    user_service = UserService(sess)
    
    joined_forums = forum_service.get_joined_forums(session['user_id'])
    
    user = g.current_user
    interests = [h.name for h in user.hobbies]
    recommended_forums = forum_service.get_recommended_forums(session['user_id'], interests)
    
    return render_template('forums.html', joined_forums=joined_forums, 
                            recommended_forums=recommended_forums, interests_list=Config.INTERESTS)

@forum_bp.route('/forums/search')
@login_required
def search_forums():
    sess = db.session
    forum_service = ForumService(sess)
    
    query = request.args.get('q', '')
    filter_by = request.args.get('filter', 'activity')
    interest = request.args.get('interest', '')
    
    results = forum_service.search_forums(query, filter_by, interest if interest else None)
    
    return render_template('forum_search_results.html', forums=results, query=query)

@forum_bp.route('/forum/<int:forum_id>')
@login_required
def forum_detail(forum_id):
    sess = db.session
    forum_service = ForumService(sess)
    post_service = PostService(sess)
    ban_service = BanService(sess)
    user_service = UserService(sess)
    
    forum = forum_service.get_by_id(forum_id)
    
    if not forum:
        flash('Forum not found', 'error')
        return redirect(url_for('forum.forums'))
    
    forum['interest_tags'] = json.loads(forum['interest_tags']) if forum['interest_tags'] else []
    
    is_member = forum_service.is_member(forum_id, session['user_id'])
    is_moderator = forum_service.is_moderator(forum_id, session['user_id'])
    is_banned = ban_service.is_banned(session['user_id'], forum_id)
    
    posts = post_service.get_by_forum(forum_id)
    for post in posts:
        post_user = User.query.get(post['user_id'])
        post['age'] = user_service.calculate_age(post_user.date_of_birth) if post_user else 0
        post['is_liked'] = post_service.is_liked_by(post['id'], session['user_id'])

    forum['moderators'] = forum_service.get_moderators(forum_id)
    
    return render_template('forum_detail.html', forum=forum, posts=posts,
                            is_member=is_member, is_moderator=is_moderator, is_banned=is_banned)

@forum_bp.route('/forum/create', methods=['GET', 'POST'])
@login_required
def create_forum():
    if request.method == 'POST':
        sess = db.session
        forum_service = ForumService(sess)
        
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        rules = request.form.get('rules', '').strip()
        is_private = request.form.get('is_private') == 'on'
        interest_tags = request.form.getlist('interest_tags')
        
        # Simple Image Upload Logic
        banner_path = None
        if 'banner' in request.files:
            file = request.files['banner']
            if file and file.filename != '':
                # Uses the standard process_post_image from utils.py
                # Saves to static/uploads/posts/
                banner_path = process_post_image(file)
                
                if not banner_path:
                    flash('Invalid image format. Allowed: jpg, png, webp', 'error')
                    return render_template('create_forum.html', interests_list=Config.INTERESTS)

        # Content Moderation
        text_fields = {
            'Forum Name': name,
            'Description': description,
            'Rules': rules
        }
        
        # Check moderation (convert /static/ path to local path for checker)
        image_check_path = banner_path.replace('/static/', 'static/') if banner_path else None
        moderation_result = moderate_content(text_fields=text_fields, image_path=image_check_path)
        
        if moderation_result['flagged']:
            return render_template('moderation_error.html',
                                error_message=moderation_result['message'],
                                return_url=url_for('forum.forums'))
        
        # Validate and Create
        errors = forum_service.validate_creation(session['user_id'], name, description)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('create_forum.html', interests_list=Config.INTERESTS)
        
        forum_id = forum_service.create(
            name=name, 
            description=description, 
            creator_id=session['user_id'], 
            is_private=is_private, 
            interest_tags=interest_tags, 
            rules=rules, 
            banner=banner_path
        )
        
        flash('Forum created successfully', 'success')
        return redirect(url_for('forum.forum_detail', forum_id=forum_id))
    
    return render_template('create_forum.html', interests_list=Config.INTERESTS)

@forum_bp.route('/forum/<int:forum_id>/join', methods=['POST'])
@login_required
def join_forum(forum_id):
    sess = db.session
    forum_service = ForumService(sess)
    
    if forum_service.join(forum_id, session['user_id']):
        flash('Joined forum successfully', 'success')
    else:
        flash('Already a member or error occurred', 'error')
    
    return redirect(url_for('forum.forum_detail', forum_id=forum_id))

@forum_bp.route('/forum/<int:forum_id>/leave', methods=['POST'])
@login_required
def leave_forum(forum_id):
    sess = db.session
    forum_service = ForumService(sess)
    
    forum_service.leave(forum_id, session['user_id'])
    flash('Left forum successfully', 'success')
    return redirect(url_for('forum.forums'))

@forum_bp.route('/upload/post-image', methods=['POST'])
@login_required
def upload_post_image():
    try:
        file = None
        if 'post_image_upload' in request.files:
            file = request.files['post_image_upload']
        
        if not file or file.filename == '':
            return jsonify({'error': 'No file provided'}), 400
        
        filepath = process_post_image(file)
        if filepath:
            # Return just the path string to match client expectation
            return filepath, 200
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@forum_bp.route('/notifications')
@login_required
def notifications():
    sess = db.session
    notif_service = NotificationService(sess)
    notifs = notif_service.get_by_user(session['user_id'])
    return render_template('notifications.html', notifications=notifs)

@forum_bp.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    sess = db.session
    notif_service = NotificationService(sess)
    notif_service.mark_as_read(notification_id)
    return jsonify({'success': True})

@forum_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    sess = db.session
    notif_service = NotificationService(sess)
    notif_service.mark_all_as_read(session['user_id'])
    return jsonify({'success': True})

@forum_bp.route('/explore')
@login_required
def explore():
    return render_template('explore.html')
    
@forum_bp.route('/hashtag/<hashtag>')
@login_required
def hashtag_posts(hashtag):
    if not hashtag.startswith('#'):
        hashtag = f'#{hashtag}'
    
    sess = db.session
    post_service = PostService(sess)
    user_service = UserService(sess)
    
    filter_by = request.args.get('filter', 'recent')
    posts = post_service.get_by_hashtag(hashtag, filter_by=filter_by)
    
    for post in posts:
        post_user = User.query.get(post['user_id'])
        post['age'] = user_service.calculate_age(post_user.birthdate) if post_user else 0
        post['is_liked'] = post_service.is_liked_by(post['id'], session['user_id'])
    
    return render_template('hashtag_posts.html', hashtag=hashtag, posts=posts, current_filter=filter_by)

@forum_bp.route('/api/search')
@login_required
def api_search():
    sess = db.session
    user_service = UserService(sess)
    forum_service = ForumService(sess)
    
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    
    if not query:
        return jsonify([])
    
    results = []
    
    if search_type in ['all', 'users']:
        users = sess.query(User).filter(
            User.username.like(f'%{query}%'),
            User.id != session['user_id']
        ).limit(10).all()
        
        for user in users:
            user_dict = user_service._user_to_dict(user)
            user_dict['type'] = 'user'
            user_dict['age'] = user_service.calculate_age(user.date_of_birth)
            results.append(user_dict)
    
    if search_type in ['all', 'forums']:
        forums = forum_service.search_forums(query, 'activity')[:5]
        for forum in forums:
            forum['type'] = 'forum'
        results.extend(forums)
    
    if search_type in ['all', 'hashtags']:
        search_query = query if query.startswith('#') else f'#{query}'
        hashtag_posts = sess.query(Post).filter(
            Post.hashtags.like(f'%{search_query}%')
        ).group_by(Post.hashtags).limit(10).all()
        
        seen_hashtags = set()
        for post in hashtag_posts:
            post_hashtags = json.loads(post.hashtags) if post.hashtags else []
            for tag in post_hashtags:
                tag_without_hash = tag.lstrip('#').lower()
                query_without_hash = query.lstrip('#').lower()
                
                if tag_without_hash.startswith(query_without_hash) and tag not in seen_hashtags:
                    results.append({
                        'type': 'hashtag',
                        'hashtag': tag,
                        'display': tag
                    })
                    seen_hashtags.add(tag)
                    if len(seen_hashtags) >= 5:
                        break
            if len(seen_hashtags) >= 5:
                break
    
    return jsonify(results)

@forum_bp.route('/api/search-following')
@login_required
def api_search_following():
    sess = db.session
    user_service = UserService(sess)
    
    query = request.args.get('q', '')
    
    if not query:
        return jsonify([])
    
    # Get users that current user follows
    following = user_service.get_following(session['user_id'])
    
    # Filter by query
    results = []
    for user in following:
        if query.lower() in user['username'].lower():
            user['age'] = user_service.calculate_age(user['birthdate'])
            results.append(user)
    
    return jsonify(results[:10])
