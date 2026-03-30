from flask import Blueprint, render_template, redirect, url_for, flash, request, session
import time

# Simple rate limiter: max 10 login attempts per minute per IP
_login_attempts = {}

def rate_limit_login():
    ip  = request.remote_addr
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < 60]  # keep last 60s
    if len(attempts) >= 10:
        return False
    attempts.append(now)
    _login_attempts[ip] = attempts
    return True
from db.users import (create_user, get_user_by_identifier, get_user_by_email,
                      verify_password, set_reset_token, reset_password as db_reset_password,
                      get_user_by_username, update_user_field)
from utils.auth import login_user, logout_user

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ── These emails are ALWAYS admin ─────────────────────────────
ADMIN_EMAILS = {
    'lakshmisundar4410@gmail.com',
}

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register.html')
        if get_user_by_username(username):
            flash('Username already taken.', 'danger')
            return render_template('auth/register.html')
        if get_user_by_email(email):
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')

        try:
            user = create_user(username, email, password)
            # Auto-promote if email is in admin list
            if email in ADMIN_EMAILS:
                update_user_field(user['id'], 'role', 'admin')
                flash('Account created! You have been granted Admin access.', 'success')
            else:
                flash('Account created! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('Registration failed. Try again.', 'danger')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        if not rate_limit_login():
            flash('Too many login attempts. Please wait 1 minute.', 'danger')
            return render_template('auth/login.html')

        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')

        user = get_user_by_identifier(identifier)
        if not user or not verify_password(user, password):
            flash('Invalid credentials.', 'danger')
            return render_template('auth/login.html')
        if user['is_banned']:
            flash('Your account is banned. Contact support.', 'danger')
            return render_template('auth/login.html')

        # Auto-promote admin emails on login too (in case they registered before)
        if user['email'] in ADMIN_EMAILS and user['role'] != 'admin':
            update_user_field(user['id'], 'role', 'admin')
            user['role'] = 'admin'

        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = get_user_by_email(email)
        if user:
            token     = set_reset_token(email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(f'Reset link (dev mode): {reset_url}', 'info')
        else:
            flash('If that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if db_reset_password(token, password):
            flash('Password updated! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired reset link.', 'danger')
            return redirect(url_for('auth.forgot_password'))
    return render_template('auth/reset_password.html', token=token)
