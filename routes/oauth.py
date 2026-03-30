"""
OAuth routes - Google, GitHub, Microsoft login
Uses requests + OAuth2 flow (no flask-dance needed)
"""
import os, secrets, json
from flask import Blueprint, redirect, url_for, request, session, flash
from db.users import get_user_by_email, create_user, get_user_by_id
from db.database import get_db, _USE_POSTGRES
from utils.auth import login_user
import urllib.parse
import urllib.request

oauth_bp = Blueprint('oauth', __name__, url_prefix='/oauth')

# ── Helper to upsert OAuth user ───────────────────────────────
def find_or_create_oauth_user(email, name, provider):
    """Find existing user by email or create one from OAuth."""
    email = email.lower().strip()
    user  = get_user_by_email(email)
    if user:
        return user
    # Create new user from OAuth — no password needed
    import re, secrets as _s
    username = re.sub(r'[^a-zA-Z0-9_]', '', name or email.split('@')[0])
    username = username[:20] or 'user'
    # Make username unique
    conn = get_db()
    base = username
    i    = 1
    while True:
        if _USE_POSTGRES:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE username=%s", (username,))
        else:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE username=?", (username,))
        if not c.fetchone():
            break
        username = f"{base}{i}"; i += 1
    conn.close()
    # Create with random secure password (they'll use OAuth to login)
    rand_pass = _s.token_hex(24)
    try:
        user = create_user(username, email, rand_pass)
    except Exception:
        user = get_user_by_email(email)
    return user

# ══════════════════════════════════════════════════════════════
# GOOGLE
# ══════════════════════════════════════════════════════════════
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_AUTH_URL      = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL     = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_URL      = 'https://www.googleapis.com/oauth2/v3/userinfo'

@oauth_bp.route('/google')
def google_login():
    if not GOOGLE_CLIENT_ID:
        flash('Google login is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    redirect_uri = url_for('oauth.google_callback', _external=True)
    params = urllib.parse.urlencode({
        'client_id':     GOOGLE_CLIENT_ID,
        'redirect_uri':  redirect_uri,
        'response_type': 'code',
        'scope':         'openid email profile',
        'state':         state,
        'access_type':   'online',
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")

@oauth_bp.route('/google/callback')
def google_callback():
    if request.args.get('state') != session.pop('oauth_state', None):
        flash('OAuth state mismatch. Please try again.', 'danger')
        return redirect(url_for('auth.login'))
    code = request.args.get('code')
    if not code:
        flash('Google login failed.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        redirect_uri = url_for('oauth.google_callback', _external=True)
        token_data   = urllib.parse.urlencode({
            'code': code, 'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': redirect_uri, 'grant_type': 'authorization_code',
        }).encode()
        req  = urllib.request.Request(GOOGLE_TOKEN_URL, data=token_data,
               headers={'Content-Type': 'application/x-www-form-urlencoded'})
        resp = json.loads(urllib.request.urlopen(req).read())
        access_token = resp['access_token']
        req2 = urllib.request.Request(GOOGLE_USER_URL,
               headers={'Authorization': f'Bearer {access_token}'})
        info = json.loads(urllib.request.urlopen(req2).read())
        user = find_or_create_oauth_user(info['email'], info.get('name',''), 'google')
        login_user(user)
        return redirect(url_for('dashboard.index'))
    except Exception as e:
        flash(f'Google login error: {str(e)[:80]}', 'danger')
        return redirect(url_for('auth.login'))

# ══════════════════════════════════════════════════════════════
# GITHUB
# ══════════════════════════════════════════════════════════════
GITHUB_CLIENT_ID     = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
GITHUB_AUTH_URL      = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL     = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL      = 'https://api.github.com/user'
GITHUB_EMAIL_URL     = 'https://api.github.com/user/emails'

@oauth_bp.route('/github')
def github_login():
    if not GITHUB_CLIENT_ID:
        flash('GitHub login is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    params = urllib.parse.urlencode({
        'client_id': GITHUB_CLIENT_ID,
        'scope':     'user:email',
        'state':     state,
    })
    return redirect(f"{GITHUB_AUTH_URL}?{params}")

@oauth_bp.route('/github/callback')
def github_callback():
    if request.args.get('state') != session.pop('oauth_state', None):
        flash('OAuth state mismatch.', 'danger')
        return redirect(url_for('auth.login'))
    code = request.args.get('code')
    if not code:
        flash('GitHub login failed.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        token_data = urllib.parse.urlencode({
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
        }).encode()
        req  = urllib.request.Request(GITHUB_TOKEN_URL, data=token_data,
               headers={'Accept': 'application/json',
                        'Content-Type': 'application/x-www-form-urlencoded'})
        resp = json.loads(urllib.request.urlopen(req).read())
        access_token = resp['access_token']
        # Get user info
        req2 = urllib.request.Request(GITHUB_USER_URL,
               headers={'Authorization': f'Bearer {access_token}',
                        'User-Agent': 'NoteShare-App'})
        info = json.loads(urllib.request.urlopen(req2).read())
        # Get email (may be private)
        email = info.get('email')
        if not email:
            req3  = urllib.request.Request(GITHUB_EMAIL_URL,
                    headers={'Authorization': f'Bearer {access_token}',
                             'User-Agent': 'NoteShare-App'})
            emails = json.loads(urllib.request.urlopen(req3).read())
            primary = [e for e in emails if e.get('primary') and e.get('verified')]
            email   = primary[0]['email'] if primary else emails[0]['email']
        user = find_or_create_oauth_user(email, info.get('login',''), 'github')
        login_user(user)
        return redirect(url_for('dashboard.index'))
    except Exception as e:
        flash(f'GitHub login error: {str(e)[:80]}', 'danger')
        return redirect(url_for('auth.login'))

# ══════════════════════════════════════════════════════════════
# MICROSOFT
# ══════════════════════════════════════════════════════════════
MS_CLIENT_ID     = os.environ.get('MS_CLIENT_ID', '')
MS_CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET', '')
MS_TENANT        = os.environ.get('MS_TENANT', 'common')
MS_AUTH_URL      = f'https://login.microsoftonline.com/{MS_TENANT}/oauth2/v2.0/authorize'
MS_TOKEN_URL     = f'https://login.microsoftonline.com/{MS_TENANT}/oauth2/v2.0/token'
MS_USER_URL      = 'https://graph.microsoft.com/v1.0/me'

@oauth_bp.route('/microsoft')
def microsoft_login():
    if not MS_CLIENT_ID:
        flash('Microsoft login is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    redirect_uri = url_for('oauth.microsoft_callback', _external=True)
    params = urllib.parse.urlencode({
        'client_id':     MS_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri':  redirect_uri,
        'scope':         'User.Read email openid profile',
        'state':         state,
    })
    return redirect(f"{MS_AUTH_URL}?{params}")

@oauth_bp.route('/microsoft/callback')
def microsoft_callback():
    if request.args.get('state') != session.pop('oauth_state', None):
        flash('OAuth state mismatch.', 'danger')
        return redirect(url_for('auth.login'))
    code = request.args.get('code')
    if not code:
        flash('Microsoft login failed.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        redirect_uri = url_for('oauth.microsoft_callback', _external=True)
        token_data   = urllib.parse.urlencode({
            'client_id':     MS_CLIENT_ID,
            'client_secret': MS_CLIENT_SECRET,
            'code':          code,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        }).encode()
        req  = urllib.request.Request(MS_TOKEN_URL, data=token_data,
               headers={'Content-Type': 'application/x-www-form-urlencoded'})
        resp = json.loads(urllib.request.urlopen(req).read())
        access_token = resp['access_token']
        req2 = urllib.request.Request(MS_USER_URL,
               headers={'Authorization': f'Bearer {access_token}'})
        info = json.loads(urllib.request.urlopen(req2).read())
        email = info.get('mail') or info.get('userPrincipalName', '')
        name  = info.get('displayName', '')
        user  = find_or_create_oauth_user(email, name, 'microsoft')
        login_user(user)
        return redirect(url_for('dashboard.index'))
    except Exception as e:
        flash(f'Microsoft login error: {str(e)[:80]}', 'danger')
        return redirect(url_for('auth.login'))
