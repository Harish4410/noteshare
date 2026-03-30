import os, json
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, send_from_directory, current_app, jsonify, abort)
from werkzeug.utils import secure_filename
from utils.auth import login_required, get_current_user
from utils.ai_utils import extract_text, generate_summary, generate_flashcards, generate_quiz, evaluate_note
from db.notes import (create_note, get_note, get_notes, increment_view, increment_download,
                      delete_note, toggle_like, user_liked, get_like_count,
                      toggle_bookmark, user_bookmarked, get_bookmarks,
                      add_comment, get_comments, get_comment_count, update_note_ai)
from db.chat import add_notification
from db.users import get_user_by_id

notes_bp = Blueprint('notes', __name__, url_prefix='/notes')
ALLOWED  = {'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx', 'png', 'jpg', 'jpeg'}

def allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

# ── Browse ────────────────────────────────────────────────────
@notes_bp.route('/')
def index():
    q       = request.args.get('q', '').strip()
    subject = request.args.get('subject', '').strip()
    sort    = request.args.get('sort', 'newest')
    ftype   = request.args.get('ftype', '').strip()
    page    = request.args.get('page', 1, type=int)
    is_ajax = request.args.get('ajax') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    from db.database import get_db, _USE_POSTGRES
    conn = get_db()
    ph   = '%s' if _USE_POSTGRES else '?'
    like = 'ILIKE' if _USE_POSTGRES else 'LIKE'
    where  = ["n.is_public=1", "n.is_approved=1"]
    params = []
    if q:
        where.append(f"(n.title {like} {ph} OR n.description {like} {ph} OR n.subject {like} {ph})")
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if subject:
        where.append(f"n.subject {like} {ph}")
        params.append(f'%{subject}%')
    if ftype:
        where.append(f"n.file_type = {ph}")
        params.append(ftype)

    order = {
        'popular': 'n.download_count DESC',
        'views':   'n.view_count DESC',
        'liked':   'n.download_count DESC',
    }.get(sort, 'n.created_at DESC')

    per_page = 12
    offset   = (page-1) * per_page
    sql = f"""SELECT n.*, u.username as author_username FROM notes n
              JOIN users u ON n.user_id=u.id
              WHERE {' AND '.join(where)} ORDER BY {order} LIMIT {ph} OFFSET {ph}"""
    c = conn.cursor()
    c.execute(sql, params + [per_page, offset])
    rows = c.fetchall()
    notes = [dict(r) if _USE_POSTGRES else dict(r) for r in rows]

    c.execute(f"SELECT COUNT(*) FROM notes n WHERE {' AND '.join(where)}", params)
    total = c.fetchone()[0]
    conn.close()
    total_pages = (total + per_page - 1) // per_page

    # AJAX: return JSON for infinite scroll
    if is_ajax and page > 1:
        from flask import render_template_string
        html = ''
        for note in notes:
            html += f'''<div class="col-md-6 col-lg-4">
              <div class="card p-3 h-100 note-card">
                <div class="d-flex justify-content-between align-items-start">
                  <a href="/notes/{note["id"]}" class="fw-semibold text-decoration-none">{note["title"]}</a>
                  <span class="badge bg-light text-dark border ms-1" style="font-size:.65rem">{note["file_type"].upper()}</span>
                </div>
                <div class="text-muted small mt-1">{note["subject"] or "General"} · {note["author_username"]}</div>
                <div class="mt-auto pt-2 d-flex gap-3 small text-muted">
                  <span>⬇️ {note["download_count"]}</span>
                  <span>👁 {note["view_count"]}</span>
                </div>
              </div></div>'''
        return jsonify({'html': html, 'has_more': page < total_pages})

    # Recommendations
    recommended = []
    user = get_current_user()
    if user:
        from db.database import get_db as _gdb
        conn2 = _gdb()
        c2    = conn2.cursor()
        # Find user's most viewed subject
        c2.execute(f"""SELECT n.subject, COUNT(*) as cnt FROM notes n
                       JOIN bookmarks b ON b.note_id=n.id
                       WHERE b.user_id={ph} AND n.subject != ''
                       GROUP BY n.subject ORDER BY cnt DESC LIMIT 1""", (user['id'],))
        row = c2.fetchone()
        if row:
            fav_subject = row[0]
            c2.execute(f"""SELECT n.*, u.username as author_username FROM notes n
                           JOIN users u ON n.user_id=u.id
                           WHERE n.subject={ph} AND n.is_public=1 AND n.user_id!={ph}
                           ORDER BY n.download_count DESC LIMIT 4""",
                       (fav_subject, user['id']))
            recommended = [dict(r) if _USE_POSTGRES else dict(r) for r in c2.fetchall()]
        conn2.close()

    return render_template('notes/index.html',
        notes=notes, q=q, subject=subject, sort=sort, ftype=ftype,
        page=page, total_pages=total_pages, total=total, recommended=recommended)

# ── Upload ────────────────────────────────────────────────────
@notes_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    user = get_current_user()
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject     = request.form.get('subject', '').strip()
        is_public   = 'is_public' in request.form
        file        = request.files.get('file')

        if not title:
            flash('Title is required.', 'danger')
            return render_template('notes/upload.html', user=user)
        if not file or file.filename == '':
            flash('Please select a file.', 'danger')
            return render_template('notes/upload.html', user=user)
        if not allowed(file.filename):
            flash('File type not allowed.', 'danger')
            return render_template('notes/upload.html', user=user)

        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        filename  = secure_filename(f"{user['id']}_{file.filename}")
        file.save(os.path.join(upload_dir, filename))
        ext  = filename.rsplit('.', 1)[1].lower()
        note = create_note(title, description, subject, filename, ext, user['id'], is_public)
        flash('Note uploaded!', 'success')
        return redirect(url_for('notes.view', note_id=note['id']))

    return render_template('notes/upload.html', user=user)

# ── View ──────────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>')
def view(note_id):
    note = get_note(note_id)
    if not note:
        abort(404)
    if not note['is_approved'] or not note['is_public']:
        user = get_current_user()
        if not user or (user['id'] != note['user_id'] and user['role'] != 'admin'):
            abort(403)

    increment_view(note_id)
    user          = get_current_user()
    liked         = user_liked(user['id'], note_id) if user else False
    bookmarked    = user_bookmarked(user['id'], note_id) if user else False
    comments      = get_comments(note_id)
    comment_count = get_comment_count(note_id)
    like_count    = get_like_count(note_id)

    return render_template('notes/view.html',
        note=note, user=user,
        liked=liked, bookmarked=bookmarked,
        comments=comments,
        comment_count=comment_count,
        like_count=like_count,
    )

# ── Download ──────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/download')
@login_required
def download(note_id):
    note = get_note(note_id)
    if not note:
        abort(404)
    increment_download(note_id)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'],
                               note['file_path'], as_attachment=True)

# ── Delete ────────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete(note_id):
    user = get_current_user()
    note = get_note(note_id)
    if not note:
        abort(404)
    if note['user_id'] != user['id'] and user['role'] != 'admin':
        abort(403)
    delete_note(note_id)
    flash('Note deleted.', 'info')
    return redirect(url_for('dashboard.index'))

# ── Like ──────────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/like', methods=['POST'])
@login_required
def toggle_like_route(note_id):
    user = get_current_user()
    note = get_note(note_id)
    if not note:
        return jsonify({'error': 'Not found'}), 404
    liked, count = toggle_like(user['id'], note_id)
    if liked:
        add_notification(note['user_id'], user['id'], 'like',
                         f"{user['username']} liked your note \"{note['title']}\"",
                         url_for('notes.view', note_id=note_id))
    return jsonify({'liked': liked, 'count': count})

# ── Bookmark ──────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark_route(note_id):
    user = get_current_user()
    bookmarked = toggle_bookmark(user['id'], note_id)
    return jsonify({'bookmarked': bookmarked})

# ── Comment ───────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/comment', methods=['POST'])
@login_required
def add_comment_route(note_id):
    user = get_current_user()
    note = get_note(note_id)
    body = request.form.get('body', '').strip()
    if not body:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('notes.view', note_id=note_id))
    add_comment(body, user['id'], note_id)
    add_notification(note['user_id'], user['id'], 'comment',
                     f"{user['username']} commented on \"{note['title']}\"",
                     url_for('notes.view', note_id=note_id))
    flash('Comment added.', 'success')
    return redirect(url_for('notes.view', note_id=note_id))

# ── Bookmarks page ────────────────────────────────────────────
@notes_bp.route('/bookmarks')
@login_required
def bookmarks():
    user  = get_current_user()
    notes = get_bookmarks(user['id'])
    return render_template('notes/bookmarks.html', user=user, notes=notes)

# ── AI: Summary ───────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/ai/summary', methods=['POST'])
@login_required
def ai_summary(note_id):
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    if note['ai_summary']:
        return jsonify({'summary': note['ai_summary']})
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text from file.'}), 400
    summary = generate_summary(text)
    update_note_ai(note_id, 'ai_summary', summary)
    return jsonify({'summary': summary})

# ── AI: Flashcards ────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/ai/flashcards', methods=['POST'])
@login_required
def ai_flashcards(note_id):
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    if note['ai_flashcards']:
        return jsonify({'flashcards': json.loads(note['ai_flashcards'])})
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text.'}), 400
    cards = generate_flashcards(text)
    update_note_ai(note_id, 'ai_flashcards', json.dumps(cards))
    return jsonify({'flashcards': cards})

# ── AI: Quiz ──────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/ai/quiz', methods=['POST'])
@login_required
def ai_quiz(note_id):
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    if note['ai_quiz']:
        return jsonify({'quiz': json.loads(note['ai_quiz'])})
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text.'}), 400
    quiz = generate_quiz(text)
    update_note_ai(note_id, 'ai_quiz', json.dumps(quiz))
    return jsonify({'quiz': quiz})

# ── AI: Score ─────────────────────────────────────────────────
@notes_bp.route('/<int:note_id>/ai/score', methods=['POST'])
@login_required
def ai_score(note_id):
    note = get_note(note_id)
    if not note: return jsonify({'error': 'Not found'}), 404
    if note['ai_score'] is not None:
        return jsonify({'score': note['ai_score']})
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], note['file_path'])
    text = extract_text(path)
    if not text: return jsonify({'error': 'Could not extract text.'}), 400
    score = evaluate_note(text)
    update_note_ai(note_id, 'ai_score', score)
    return jsonify({'score': score})
