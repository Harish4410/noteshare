from flask import Blueprint, render_template, redirect, url_for, flash, request
from utils.auth import login_required, get_current_user
from db.users import get_user_by_username, get_follower_count, get_following_count, is_following
from db.notes import get_feed_notes, get_user_notes, get_user_stats
from db.chat import get_notifications, mark_all_read, unread_count, get_tasks_by_status
from db.users import get_followed_ids

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    user         = get_current_user()
    followed_ids = get_followed_ids(user['id'])
    feed_notes   = get_feed_notes(followed_ids, user['id'])
    my_notes     = get_user_notes(user['id'], limit=5)
    stats        = get_user_stats(user['id'])
    notifs       = get_notifications(user['id'], unread_only=True, limit=8)
    tasks_todo   = get_tasks_by_status(user['id'], 'todo')[:5]
    tasks_doing  = get_tasks_by_status(user['id'], 'doing')[:5]

    return render_template('dashboard/index.html',
        user=user,
        feed_notes=feed_notes,
        my_notes=my_notes,
        total_notes=stats['total_notes'],
        total_downloads=stats['total_downloads'],
        total_followers=get_follower_count(user['id']),
        total_following=get_following_count(user['id']),
        notifications=notifs,
        tasks_todo=tasks_todo,
        tasks_doing=tasks_doing,
    )

@dashboard_bp.route('/profile/<username>')
@login_required
def profile(username):
    me          = get_current_user()
    profile_user= get_user_by_username(username)
    if not profile_user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard.index'))
    notes        = get_user_notes(profile_user['id'])
    following    = is_following(me['id'], profile_user['id'])
    followers    = get_follower_count(profile_user['id'])
    following_ct = get_following_count(profile_user['id'])
    return render_template('dashboard/profile.html',
        user=me,
        profile_user=profile_user,
        notes=notes,
        is_following=following,
        follower_count=followers,
        following_count=following_ct,
    )

@dashboard_bp.route('/notifications')
@login_required
def notifications():
    user  = get_current_user()
    notifs= get_notifications(user['id'], limit=50)
    mark_all_read(user['id'])
    return render_template('dashboard/notifications.html', user=user, notifications=notifs)
