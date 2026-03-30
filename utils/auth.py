"""utils/auth.py – Session-based auth."""
from functools import wraps
from flask import session, redirect, url_for, abort, g, request
from db.users import get_user_by_id, update_last_seen

def login_user(user):
    session['user_id'] = user['id']
    session.permanent  = True

def logout_user():
    session.clear()

def get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    user = get_user_by_id(uid)
    if not user:
        session.clear()
        return None
    return user

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for('auth.login', next=request.path))
        if user['is_banned']:
            session.clear()
            return redirect(url_for('auth.login'))
        update_last_seen(user['id'])
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for('auth.login'))
        if user['role'] != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated
