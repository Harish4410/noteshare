from flask import Blueprint, redirect, url_for, flash, jsonify, request, render_template, abort
from utils.auth import login_required, admin_required, get_current_user
from db.users import (follow_user, unfollow_user, is_following,
                      get_follower_count, get_following_count,
                      get_followers, get_following, get_user_by_id, get_user_by_username,
                      update_user_field, delete_user, get_all_users)
from db.notes import get_all_notes_admin, update_note_approval, delete_note, get_note
from db.chat import (create_group, get_all_groups, get_group, join_group,
                     is_member, get_group_members, delete_group,
                     send_group_message, send_private_message,
                     get_group_messages, get_private_messages,
                     get_new_group_messages, get_new_private_messages,
                     get_dm_contacts, delete_message,
                     create_task, get_tasks_by_status, update_task_status,
                     delete_task as db_delete_task,
                     create_study_plan, get_study_plans,
                     add_notification)

# ═══════════════════════════════════════════════════════════════
# SOCIAL
# ═══════════════════════════════════════════════════════════════
social_bp = Blueprint('social', __name__, url_prefix='/social')

@social_bp.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    me   = get_current_user()
    them = get_user_by_id(user_id)
    if not them or them['id'] == me['id']:
        return jsonify({'error': 'Invalid'}), 400

    if is_following(me['id'], user_id):
        unfollow_user(me['id'], user_id)
        following = False
    else:
        follow_user(me['id'], user_id)
        add_notification(user_id, me['id'], 'follow',
                         f"{me['username']} started following you.",
                         url_for('dashboard.profile', username=me['username']))
        following = True

    return jsonify({'following': following, 'followers': get_follower_count(user_id)})

@social_bp.route('/followers/<int:user_id>')
@login_required
def followers(user_id):
    me   = get_current_user()
    them = get_user_by_id(user_id)
    if not them: abort(404)
    return render_template('social/list.html', user=me,
        profile_user=them, users=get_followers(user_id), list_type='Followers')

@social_bp.route('/following/<int:user_id>')
@login_required
def following(user_id):
    me   = get_current_user()
    them = get_user_by_id(user_id)
    if not them: abort(404)
    return render_template('social/list.html', user=me,
        profile_user=them, users=get_following(user_id), list_type='Following')


# ═══════════════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════════════
chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
@login_required
def index():
    user   = get_current_user()
    groups = get_all_groups()
    return render_template('chat/index.html', user=user, groups=groups)

@chat_bp.route('/group/create', methods=['POST'])
@login_required
def create_group_route():
    user = get_current_user()
    name = request.form.get('name', '').strip()
    desc = request.form.get('description', '').strip()
    if not name:
        flash('Group name required.', 'danger')
        return redirect(url_for('chat.index'))
    gid = create_group(name, desc, user['id'])
    return redirect(url_for('chat.group', group_id=gid))

@chat_bp.route('/group/<int:group_id>')
@login_required
def group(group_id):
    user = get_current_user()
    grp  = get_group(group_id)
    if not grp: abort(404)
    if not is_member(group_id, user['id']):
        join_group(group_id, user['id'])
    messages = get_group_messages(group_id)
    members  = get_group_members(group_id)
    return render_template('chat/group.html',
        user=user, group=grp, messages=messages, members=members)

@chat_bp.route('/group/<int:group_id>/send', methods=['POST'])
@login_required
def send_group(group_id):
    user = get_current_user()
    body = request.json.get('body', '').strip()
    if not body: return jsonify({'error': 'Empty'}), 400
    msg = send_group_message(body, user['id'], group_id)
    return jsonify({'id': msg['id'], 'body': msg['body'],
                    'sender_username': msg['sender_username'],
                    'created_at': msg['created_at']})

@chat_bp.route('/group/<int:group_id>/poll')
@login_required
def poll_group(group_id):
    after = request.args.get('after', 0, type=int)
    msgs  = get_new_group_messages(group_id, after_id=after)
    return jsonify({'messages': msgs})

@chat_bp.route('/group/<int:group_id>/history')
@login_required
def group_history(group_id):
    msgs = get_group_messages(group_id)
    return jsonify({'messages': msgs})

@chat_bp.route('/private/<int:user_id>/history')
@login_required
def private_history(user_id):
    me   = get_current_user()
    msgs = get_private_messages(me['id'], user_id)
    return jsonify({'messages': msgs})

@chat_bp.route('/private/<int:user_id>')
@login_required
def private(user_id):
    me       = get_current_user()
    other    = get_user_by_id(user_id)
    if not other: abort(404)
    messages = get_private_messages(me['id'], user_id)
    contacts = get_dm_contacts(me['id'])
    return render_template('chat/private.html',
        user=me, other=other, messages=messages, contacts=contacts)

@chat_bp.route('/private/<int:user_id>/send', methods=['POST'])
@login_required
def send_private(user_id):
    me   = get_current_user()
    body = request.json.get('body', '').strip()
    if not body: return jsonify({'error': 'Empty'}), 400
    msg = send_private_message(body, me['id'], user_id)
    return jsonify({'id': msg['id'], 'body': msg['body'],
                    'sender_username': msg['sender_username'],
                    'created_at': msg['created_at']})

@chat_bp.route('/private/<int:user_id>/poll')
@login_required
def poll_private(user_id):
    me    = get_current_user()
    after = request.args.get('after', 0, type=int)
    msgs  = get_new_private_messages(me['id'], user_id, after_id=after)
    return jsonify({'messages': msgs})

@chat_bp.route('/message/<int:msg_id>/delete', methods=['POST'])
@login_required
def del_message(msg_id):
    delete_message(msg_id)
    return jsonify({'deleted': True})

@chat_bp.route('/search-users')
@login_required
def search_users():
    from db.database import get_db
    me  = get_current_user()
    q   = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'users': []})
    conn  = get_db()
    rows  = conn.execute(
        "SELECT id, username FROM users WHERE username LIKE ? AND id != ? LIMIT 8",
        (f'%{q}%', me['id'])
    ).fetchall()
    conn.close()
    return jsonify({'users': [dict(r) for r in rows]})


# ═══════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@admin_required
def index():
    from db.database import get_db, dict_cursor
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); tu = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM notes"); tn = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM notes WHERE is_approved=0"); tp = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1"); tb = c.fetchone()[0]
    conn.close()
    stats = {'total_users': tu, 'total_notes': tn, 'pending': tp, 'banned_users': tb}
    recent_users, _ = get_all_users(page=1, per_page=8)
    recent_notes, _ = get_all_notes_admin(page=1, per_page=8)
    user = get_current_user()
    return render_template('admin/index.html', user=user, stats=stats,
                           recent_users=recent_users, recent_notes=recent_notes)

@admin_bp.route('/users')
@admin_required
def users():
    user = get_current_user()
    q    = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    users_list, total = get_all_users(search=q, page=page)
    total_pages = (total + 19) // 20
    return render_template('admin/users.html', user=user, users=users_list,
                           q=q, page=page, total_pages=total_pages)

@admin_bp.route('/users/<int:uid>/ban', methods=['POST'])
@admin_required
def ban_user(uid):
    target = get_user_by_id(uid)
    if target and target['role'] != 'admin':
        new_val = 0 if target['is_banned'] else 1
        update_user_field(uid, 'is_banned', new_val)
        flash(f"User {'banned' if new_val else 'unbanned'}.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:uid>/promote', methods=['POST'])
@admin_required
def promote_user(uid):
    target = get_user_by_id(uid)
    if target:
        new_role = 'user' if target['role'] == 'admin' else 'admin'
        update_user_field(uid, 'role', new_role)
        flash(f"User is now {new_role}.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user_route(uid):
    me = get_current_user()
    if uid == me['id']:
        flash('Cannot delete yourself.', 'danger')
    else:
        delete_user(uid)
        flash('User deleted.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/notes')
@admin_required
def notes():
    user   = get_current_user()
    status = request.args.get('status', 'all')
    page   = request.args.get('page', 1, type=int)
    notes_list, total = get_all_notes_admin(status=status, page=page)
    total_pages = (total + 19) // 20
    return render_template('admin/notes.html', user=user, notes=notes_list,
                           status=status, page=page, total_pages=total_pages)

@admin_bp.route('/notes/<int:note_id>/approve', methods=['POST'])
@admin_required
def approve_note(note_id):
    update_note_approval(note_id, True)
    flash('Note approved.', 'success')
    return redirect(url_for('admin.notes'))

@admin_bp.route('/notes/<int:note_id>/reject', methods=['POST'])
@admin_required
def reject_note(note_id):
    update_note_approval(note_id, False)
    flash('Note rejected.', 'warning')
    return redirect(url_for('admin.notes'))

@admin_bp.route('/notes/<int:note_id>/delete', methods=['POST'])
@admin_required
def delete_note_route(note_id):
    delete_note(note_id)
    flash('Note deleted.', 'success')
    return redirect(url_for('admin.notes'))

@admin_bp.route('/chats')
@admin_required
def chats():
    user   = get_current_user()
    groups = get_all_groups()
    return render_template('admin/chats.html', user=user, groups=groups)

@admin_bp.route('/chats/<int:group_id>/delete', methods=['POST'])
@admin_required
def delete_group_route(group_id):
    delete_group(group_id)
    flash('Group deleted.', 'success')
    return redirect(url_for('admin.chats'))


# ═══════════════════════════════════════════════════════════════
# STUDY PLANNER
# ═══════════════════════════════════════════════════════════════
study_bp = Blueprint('study', __name__, url_prefix='/study')

@study_bp.route('/')
@login_required
def index():
    user  = get_current_user()
    todo  = get_tasks_by_status(user['id'], 'todo')
    doing = get_tasks_by_status(user['id'], 'doing')
    done  = get_tasks_by_status(user['id'], 'done')
    plans = get_study_plans(user['id'])
    return render_template('study/index.html',
        user=user, todo=todo, doing=doing, done=done, plans=plans)

@study_bp.route('/task/create', methods=['POST'])
@login_required
def create_task_route():
    user  = get_current_user()
    title = request.form.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    tid = create_task(
        title=title,
        description=request.form.get('description', ''),
        priority=request.form.get('priority', 'medium'),
        due_date=request.form.get('due_date') or None,
        user_id=user['id']
    )
    return jsonify({'id': tid, 'title': title, 'status': 'todo'})

@study_bp.route('/task/<int:task_id>/status', methods=['POST'])
@login_required
def task_status(task_id):
    user   = get_current_user()
    status = request.json.get('status')
    if status in ('todo', 'doing', 'done'):
        update_task_status(task_id, status, user['id'])
    return jsonify({'ok': True})

@study_bp.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task_route(task_id):
    user = get_current_user()
    db_delete_task(task_id, user['id'])
    return jsonify({'deleted': True})

@study_bp.route('/plan/create', methods=['POST'])
@login_required
def create_plan():
    user    = get_current_user()
    title   = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if title and content:
        create_study_plan(title, content, user['id'])
        flash('Study plan saved!', 'success')
    return redirect(url_for('study.index'))
