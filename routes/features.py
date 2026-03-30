"""
routes/features.py
All new feature routes: AI chatbot, live notifications,
live search, analytics, gamification, leaderboard, exam mode,
note versions, AI improvement, smart search
"""
import json, os
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, abort
from utils.auth import login_required, get_current_user
from db.database import get_db, _USE_POSTGRES
from db.notes    import get_notes, get_note
from db.chat     import get_notifications, unread_count, mark_all_read
import urllib.request

features_bp = Blueprint('features', __name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def _call_gemini(prompt):
    if not GEMINI_API_KEY: return "AI not configured. Add GEMINI_API_KEY to .env"
    try:
        payload = json.dumps({"contents":[{"parts":[{"text":prompt}]}],
                              "generationConfig":{"temperature":0.5,"maxOutputTokens":800}}).encode()
        req = urllib.request.Request(f"{GEMINI_URL}?key={GEMINI_API_KEY}",
              data=payload, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        return f"AI error: {str(e)[:80]}"

# ── AI Chatbot ────────────────────────────────────────────────
@features_bp.route('/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    data     = request.json
    question = data.get('question', '').strip()
    note_id  = data.get('note_id')
    history  = data.get('history', [])

    context = ""
    if note_id:
        note = get_note(note_id)
        if note and note.get('ai_summary'):
            context = f"Context from the note '{note['title']}':\n{note['ai_summary']}\n\n"
        elif note:
            from utils.ai_utils import extract_text
            path = os.path.join(os.getcwd(), 'uploads', note['file_path'])
            text = extract_text(path)
            if text: context = f"Note content:\n{text[:2000]}\n\n"

    hist_text = ""
    for h in history[-4:]:
        role = "Student" if h['role'] == 'user' else "Assistant"
        hist_text += f"{role}: {h['content']}\n"

    prompt = f"""You are a helpful academic study assistant for students.
{context}
{hist_text}
Student: {question}

Give a clear, helpful answer. Keep it concise but complete. Use examples if helpful."""

    answer = _call_gemini(prompt)
    return jsonify({'answer': answer})

# ── AI Note Improvement ───────────────────────────────────────
@features_bp.route('/notes/<int:note_id>/ai/improve', methods=['POST'])
@login_required
def ai_improve(note_id):
    from utils.ai_utils import extract_text
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    path = os.path.join(os.getcwd(), 'uploads', note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text'}), 400

    prompt = f"""Improve these academic notes. Make them:
1. Better structured with clear headings
2. Grammar and spelling corrected
3. Key concepts highlighted with **bold**
4. Missing important topics suggested at the end

Original notes:
{text[:3000]}

Return the improved notes in markdown format."""

    improved = _call_gemini(prompt)
    return jsonify({'improved': improved})

# ── AI Suggest Missing Topics ─────────────────────────────────
@features_bp.route('/notes/<int:note_id>/ai/suggest', methods=['POST'])
@login_required
def ai_suggest(note_id):
    from utils.ai_utils import extract_text
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    path = os.path.join(os.getcwd(), 'uploads', note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text'}), 400

    prompt = f"""Analyze these academic notes on "{note['title']}" ({note['subject']}).
List 5 important topics that are MISSING from these notes.
Format as a simple numbered list.

Notes:
{text[:2000]}"""

    result = _call_gemini(prompt)
    return jsonify({'suggestions': result})

# ── Live Search ───────────────────────────────────────────────
@features_bp.route('/search/live')
def live_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': []})
    notes, _ = get_notes(search=q, page=1, per_page=6)
    results  = [{'id': n['id'], 'title': n['title'],
                 'subject': n.get('subject',''), 'author': n['author_username']}
                for n in notes]
    return jsonify({'results': results})

# ── Live Notifications ────────────────────────────────────────
@features_bp.route('/notifications/live')
@login_required
def notifs_live():
    user  = get_current_user()
    after = request.args.get('after', 0, type=int)
    conn  = get_db()
    ph    = '%s' if _USE_POSTGRES else '?'
    c     = conn.cursor()
    c.execute(f"SELECT * FROM notifications WHERE user_id={ph} AND id>{ph} ORDER BY id DESC LIMIT 5",
              (user['id'], after))
    rows  = [dict(r) if not _USE_POSTGRES else r for r in c.fetchall()]
    if not _USE_POSTGRES:
        rows = [dict(r) for r in rows]
    unread = unread_count(user['id'])
    conn.close()
    return jsonify({'notifications': rows, 'unread_count': unread})

@features_bp.route('/notifications/dropdown')
@login_required
def notifs_dropdown():
    user  = get_current_user()
    notifs = get_notifications(user['id'], limit=10)
    mark_all_read(user['id'])
    return jsonify({'notifications': [dict(n) for n in notifs]})

# ── Analytics Dashboard ───────────────────────────────────────
@features_bp.route('/analytics')
@login_required
def analytics():
    user = get_current_user()
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    c    = conn.cursor()

    # Views over last 7 days
    c.execute(f"""SELECT date(created_at) as day, SUM(view_count) as views
                  FROM notes WHERE user_id={ph}
                  GROUP BY date(created_at) ORDER BY day DESC LIMIT 7""", (user['id'],))
    views_data = [dict(r) if _USE_POSTGRES else {'day': r[0], 'views': r[1]} for r in c.fetchall()]

    # Top notes by views
    c.execute(f"""SELECT title, view_count, download_count, like_count
                  FROM notes n
                  LEFT JOIN (SELECT note_id, COUNT(*) as like_count FROM note_likes GROUP BY note_id) l
                  ON n.id=l.note_id
                  WHERE user_id={ph} ORDER BY view_count DESC LIMIT 5""", (user['id'],))
    top_notes = []
    for r in c.fetchall():
        if _USE_POSTGRES: top_notes.append(dict(r))
        else: top_notes.append({'title':r[0],'view_count':r[1],'download_count':r[2],'like_count':r[3] or 0})

    # Trending notes (all users, last 7 days)
    c.execute("""SELECT n.title, n.view_count, n.download_count, u.username as author
                 FROM notes n JOIN users u ON n.user_id=u.id
                 WHERE n.is_public=1 AND n.is_approved=1
                 ORDER BY (n.view_count + n.download_count*2) DESC LIMIT 5""")
    trending = []
    for r in c.fetchall():
        if _USE_POSTGRES: trending.append(dict(r))
        else: trending.append({'title':r[0],'view_count':r[1],'download_count':r[2],'author':r[3]})

    # Popular subjects
    c.execute("""SELECT subject, COUNT(*) as cnt FROM notes
                 WHERE subject != '' AND is_public=1
                 GROUP BY subject ORDER BY cnt DESC LIMIT 6""")
    subjects = []
    for r in c.fetchall():
        if _USE_POSTGRES: subjects.append(dict(r))
        else: subjects.append({'subject': r[0], 'cnt': r[1]})

    # Platform stats
    c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM notes WHERE is_public=1"); total_notes = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(download_count),0) FROM notes"); total_dl = c.fetchone()[0]

    conn.close()
    return render_template('features/analytics.html',
        user=user, views_data=views_data, top_notes=top_notes,
        trending=trending, subjects=subjects,
        total_users=total_users, total_notes=total_notes, total_downloads=total_dl)

# ── Gamification ──────────────────────────────────────────────
BADGES = [
    {'id':'first_upload', 'name':'First Upload',  'icon':'📤', 'desc':'Upload your first note', 'xp':50},
    {'id':'ten_uploads',  'name':'Note Creator',   'icon':'📚', 'desc':'Upload 10 notes',        'xp':200},
    {'id':'popular',      'name':'Popular',        'icon':'🔥', 'desc':'Get 10 likes',           'xp':150},
    {'id':'helper',       'name':'Helper',         'icon':'💬', 'desc':'Post 5 comments',        'xp':100},
    {'id':'social',       'name':'Social',         'icon':'👥', 'desc':'Get 5 followers',        'xp':100},
    {'id':'scholar',      'name':'Scholar',        'icon':'🎓', 'desc':'Download 20 notes',      'xp':200},
    {'id':'top_contrib',  'name':'Top Contributor','icon':'🥇', 'desc':'Most uploads this month','xp':500},
    {'id':'ai_master',    'name':'AI Master',      'icon':'🤖', 'desc':'Use AI on 5 notes',      'xp':150},
]

def _get_user_xp_badges(user_id):
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    c    = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM notes WHERE user_id={ph}", (user_id,)); note_count = c.fetchone()[0]
    c.execute(f"SELECT COALESCE(SUM(like_count),0) FROM (SELECT COUNT(*) as like_count FROM note_likes nl JOIN notes n ON nl.note_id=n.id WHERE n.user_id={ph}) t", (user_id,))
    like_count = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM comments WHERE user_id={ph}", (user_id,)); comment_count = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM follows WHERE followed_id={ph}", (user_id,)); follower_count = c.fetchone()[0]
    conn.close()

    earned = set()
    if note_count >= 1:  earned.add('first_upload')
    if note_count >= 10: earned.add('ten_uploads')
    if like_count >= 10: earned.add('popular')
    if comment_count >= 5: earned.add('helper')
    if follower_count >= 5: earned.add('social')

    xp = sum(b['xp'] for b in BADGES if b['id'] in earned)
    level = 1 + xp // 200
    return earned, xp, level

@features_bp.route('/gamification')
@login_required
def gamification():
    user   = get_current_user()
    earned, xp, level = _get_user_xp_badges(user['id'])
    # Leaderboard
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    c    = conn.cursor()
    c.execute("""SELECT u.id, u.username,
                 COUNT(n.id) as note_count,
                 COALESCE(SUM(n.download_count),0) as total_downloads,
                 COALESCE(SUM(n.view_count),0) as total_views
                 FROM users u LEFT JOIN notes n ON u.id=n.user_id
                 GROUP BY u.id, u.username
                 ORDER BY (COUNT(n.id)*10 + COALESCE(SUM(n.download_count),0)*5) DESC LIMIT 10""")
    leaderboard = []
    for r in c.fetchall():
        if _USE_POSTGRES: leaderboard.append(dict(r))
        else: leaderboard.append({'id':r[0],'username':r[1],'note_count':r[2],'total_downloads':r[3],'total_views':r[4]})
    conn.close()
    next_xp = (level) * 200
    return render_template('features/gamification.html',
        user=user, badges=BADGES, earned=earned,
        xp=xp, level=level, next_xp=next_xp,
        leaderboard=leaderboard)

# ── Note Version Control ──────────────────────────────────────
@features_bp.route('/notes/<int:note_id>/versions')
@login_required
def note_versions(note_id):
    user = get_current_user()
    note = get_note(note_id)
    if not note or note['user_id'] != user['id']: abort(403)
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    c    = conn.cursor()
    # Create versions table if not exists
    conn.execute("""CREATE TABLE IF NOT EXISTS note_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id INTEGER NOT NULL, content TEXT, version_num INTEGER,
        created_at TEXT DEFAULT (datetime('now')))""")
    conn.commit()
    c.execute(f"SELECT * FROM note_versions WHERE note_id={ph} ORDER BY version_num DESC", (note_id,))
    rows = [dict(r) if _USE_POSTGRES else dict(r) for r in c.fetchall()]
    conn.close()
    return render_template('features/versions.html', user=user, note=note, versions=rows)

@features_bp.route('/notes/<int:note_id>/version', methods=['POST'])
@login_required
def save_version(note_id):
    user    = get_current_user()
    content = request.json.get('content', '')
    conn    = get_db()
    ph      = '%s' if _USE_POSTGRES else '?'
    conn.execute("""CREATE TABLE IF NOT EXISTS note_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id INTEGER NOT NULL, content TEXT, version_num INTEGER,
        created_at TEXT DEFAULT (datetime('now')))""")
    c = conn.cursor()
    c.execute(f"SELECT COALESCE(MAX(version_num),0) FROM note_versions WHERE note_id={ph}", (note_id,))
    next_v = (c.fetchone()[0] or 0) + 1
    c.execute(f"INSERT INTO note_versions (note_id, content, version_num) VALUES ({ph},{ph},{ph})",
              (note_id, content, next_v))
    conn.commit(); conn.close()
    return jsonify({'version': next_v})

# ── Exam Score Save ───────────────────────────────────────────
@features_bp.route('/study/exam-score', methods=['POST'])
@login_required
def save_exam_score():
    return jsonify({'ok': True})  # Future: save to DB

# ── Dashboard Analytics Data API ──────────────────────────────
@features_bp.route('/analytics/data')
@login_required
def analytics_data():
    user = get_current_user()
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    c    = conn.cursor()

    # Views per day (last 7 days) for this user
    c.execute(f"""SELECT date(created_at) as day, SUM(view_count) as views
                  FROM notes WHERE user_id={ph}
                  GROUP BY date(created_at) ORDER BY day DESC LIMIT 7""", (user['id'],))
    rows = c.fetchall()
    views = [{'day': r[0], 'views': r[1] or 0} for r in rows] if rows else []

    # Popular subjects platform-wide
    c.execute("""SELECT subject, COUNT(*) as cnt FROM notes
                 WHERE subject != '' AND is_public=1
                 GROUP BY subject ORDER BY cnt DESC LIMIT 5""")
    rows = c.fetchall()
    subjects = [{'subject': r[0], 'cnt': r[1]} for r in rows]

    # Trending notes
    c.execute("""SELECT n.id, n.title, n.subject, n.view_count, n.download_count
                 FROM notes n WHERE n.is_public=1 AND n.is_approved=1
                 ORDER BY (n.view_count + n.download_count*2) DESC LIMIT 5""")
    rows = c.fetchall()
    trending = [{'id':r[0],'title':r[1],'subject':r[2],'view_count':r[3],'download_count':r[4]} for r in rows]

    conn.close()
    return jsonify({'views': views, 'subjects': subjects, 'trending': trending})

# ── Course-wise Notes ──────────────────────────────────────────
@features_bp.route('/courses')
@login_required
def courses():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""SELECT subject, COUNT(*) as cnt,
                 SUM(download_count) as total_downloads
                 FROM notes WHERE is_public=1 AND is_approved=1 AND subject != ''
                 GROUP BY subject ORDER BY cnt DESC""")
    rows    = c.fetchall()
    courses = [{'subject':r[0],'cnt':r[1],'downloads':r[2]} for r in rows]
    conn.close()
    return render_template('features/courses.html', courses=courses)
