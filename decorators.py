from functools import wraps
from flask import g, flash, redirect, url_for, session

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not getattr(g, 'current_user', None):
            session.clear()
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_user or not g.current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('forum.feed')) # Redirect to feed instead of index
        return f(*args, **kwargs)
    return decorated_function
