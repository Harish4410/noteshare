"""db/notes.py – Works with both PostgreSQL and SQLite."""
from .database import get_db, dict_cursor, _USE_POSTGRES

def _p(n=1):
    return '%s' if _USE_POSTGRES else '?'

def _fmt_row(r):
    if r is None: return None
    return dict(r)

def create_note(title, description, subject, file_path, file_type, user_id, is_public=True):
    conn = get_db()
    pub  = 1 if is_public else 0
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute("INSERT INTO notes (title,description,subject,file_path,file_type,user_id,is_public) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                  (title, description, subject, file_path, file_type, user_id, pub))
        note_id = c.fetchone()['id']
    else:
        c = conn.cursor()
        c.execute("INSERT INTO notes (title,description,subject,file_path,file_type,user_id,is_public) VALUES (?,?,?,?,?,?,?)",
                  (title, description, subject, file_path, file_type, user_id, pub))
        note_id = c.lastrowid
    conn.commit(); conn.close()
    return get_note(note_id)

def get_note(note_id):
    conn = get_db()
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute("SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE n.id=%s", (note_id,))
        row = c.fetchone()
    else:
        c = conn.cursor()
        c.execute("SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE n.id=?", (note_id,))
        row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_notes(search='', subject='', page=1, per_page=12, approved_only=True):
    conn   = get_db()
    offset = (page - 1) * per_page
    where  = ["n.is_public=1"]
    params = []
    like_op = "ILIKE" if _USE_POSTGRES else "LIKE"
    ph      = "%s" if _USE_POSTGRES else "?"
    if approved_only:
        where.append("n.is_approved=1")
    if search:
        where.append(f"(n.title {like_op} {ph} OR n.description {like_op} {ph} OR n.subject {like_op} {ph})")
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if subject:
        where.append(f"n.subject {like_op} {ph}")
        params.append(f'%{subject}%')
    sql = f"SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE {' AND '.join(where)} ORDER BY n.created_at DESC LIMIT {ph} OFFSET {ph}"
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute(sql, params + [per_page, offset])
        rows = c.fetchall()
        c.execute(f"SELECT COUNT(*) as n FROM notes n WHERE {' AND '.join(where)}", params)
        total = c.fetchone()['n']
    else:
        c = conn.cursor()
        c.execute(sql, params + [per_page, offset])
        rows = [dict(r) for r in c.fetchall()]
        c.execute(f"SELECT COUNT(*) FROM notes n WHERE {' AND '.join(where)}", params)
        total = c.fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total

def get_feed_notes(followed_ids, own_id, limit=20):
    ids  = list(followed_ids) + [own_id]
    conn = get_db()
    ph   = "%s" if _USE_POSTGRES else "?"
    placeholders = ','.join([ph] * len(ids))
    sql  = f"SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE n.user_id IN ({placeholders}) AND n.is_approved=1 AND n.is_public=1 ORDER BY n.created_at DESC LIMIT {ph}"
    if _USE_POSTGRES:
        c = dict_cursor(conn); c.execute(sql, ids + [limit]); rows = c.fetchall()
    else:
        c = conn.cursor(); c.execute(sql, ids + [limit]); rows = [dict(r) for r in c.fetchall()]
    conn.close(); return rows

def get_user_notes(user_id, limit=None):
    conn = get_db()
    ph   = "%s" if _USE_POSTGRES else "?"
    sql  = f"SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE n.user_id={ph} ORDER BY n.created_at DESC"
    if limit: sql += f" LIMIT {int(limit)}"
    if _USE_POSTGRES:
        c = dict_cursor(conn); c.execute(sql, (user_id,)); rows = c.fetchall()
    else:
        c = conn.cursor(); c.execute(sql, (user_id,)); rows = [dict(r) for r in c.fetchall()]
    conn.close(); return rows

def _simple_update(sql_pg, sql_sq, params):
    conn = get_db()
    if _USE_POSTGRES: conn.cursor().execute(sql_pg, params)
    else: conn.execute(sql_sq, params)
    conn.commit(); conn.close()

def increment_view(note_id):
    _simple_update("UPDATE notes SET view_count=view_count+1 WHERE id=%s",
                   "UPDATE notes SET view_count=view_count+1 WHERE id=?", (note_id,))

def increment_download(note_id):
    _simple_update("UPDATE notes SET download_count=download_count+1 WHERE id=%s",
                   "UPDATE notes SET download_count=download_count+1 WHERE id=?", (note_id,))

def update_note_ai(note_id, field, value):
    allowed = {'ai_score', 'ai_summary', 'ai_flashcards', 'ai_quiz'}
    if field not in allowed: return
    _simple_update(f"UPDATE notes SET {field}=%s WHERE id=%s",
                   f"UPDATE notes SET {field}=? WHERE id=?", (value, note_id))

def update_note_approval(note_id, approved):
    v = 1 if approved else 0
    _simple_update("UPDATE notes SET is_approved=%s WHERE id=%s",
                   "UPDATE notes SET is_approved=? WHERE id=?", (v, note_id))

def delete_note(note_id):
    _simple_update("DELETE FROM notes WHERE id=%s", "DELETE FROM notes WHERE id=?", (note_id,))

def get_all_notes_admin(status='all', page=1, per_page=20):
    conn   = get_db()
    offset = (page - 1) * per_page
    ph     = "%s" if _USE_POSTGRES else "?"
    where  = "1=1"
    params = []
    if status == 'pending':  where = "n.is_approved=0"
    elif status == 'approved': where = "n.is_approved=1"
    sql = f"SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id WHERE {where} ORDER BY n.created_at DESC LIMIT {ph} OFFSET {ph}"
    if _USE_POSTGRES:
        c = dict_cursor(conn); c.execute(sql, params+[per_page,offset]); rows = c.fetchall()
        c.execute(f"SELECT COUNT(*) as n FROM notes n WHERE {where}", params); total = c.fetchone()['n']
    else:
        c = conn.cursor(); c.execute(sql, params+[per_page,offset]); rows = [dict(r) for r in c.fetchall()]
        c.execute(f"SELECT COUNT(*) FROM notes n WHERE {where}", params); total = c.fetchone()[0]
    conn.close(); return [dict(r) for r in rows], total

def toggle_like(user_id, note_id):
    conn = get_db()
    if _USE_POSTGRES:
        c = conn.cursor()
        c.execute("SELECT 1 FROM note_likes WHERE user_id=%s AND note_id=%s", (user_id, note_id))
        if c.fetchone():
            c.execute("DELETE FROM note_likes WHERE user_id=%s AND note_id=%s", (user_id, note_id)); liked=False
        else:
            c.execute("INSERT INTO note_likes (user_id, note_id) VALUES (%s,%s)", (user_id, note_id)); liked=True
        conn.commit()
        c.execute("SELECT COUNT(*) FROM note_likes WHERE note_id=%s", (note_id,)); count=c.fetchone()[0]
    else:
        c = conn.cursor()
        c.execute("SELECT 1 FROM note_likes WHERE user_id=? AND note_id=?", (user_id, note_id))
        if c.fetchone():
            conn.execute("DELETE FROM note_likes WHERE user_id=? AND note_id=?", (user_id, note_id)); liked=False
        else:
            conn.execute("INSERT OR IGNORE INTO note_likes (user_id, note_id) VALUES (?,?)", (user_id, note_id)); liked=True
        conn.commit()
        c.execute("SELECT COUNT(*) FROM note_likes WHERE note_id=?", (note_id,)); count=c.fetchone()[0]
    conn.close(); return liked, count

def user_liked(user_id, note_id):
    conn = get_db(); c = conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT 1 FROM note_likes WHERE user_id=%s AND note_id=%s", (user_id, note_id))
    else: c.execute("SELECT 1 FROM note_likes WHERE user_id=? AND note_id=?", (user_id, note_id))
    row=c.fetchone(); conn.close(); return row is not None

def get_like_count(note_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT COUNT(*) FROM note_likes WHERE note_id=%s",(note_id,))
    else: c.execute("SELECT COUNT(*) FROM note_likes WHERE note_id=?",(note_id,))
    n=c.fetchone()[0]; conn.close(); return n

def toggle_bookmark(user_id, note_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES:
        c.execute("SELECT 1 FROM bookmarks WHERE user_id=%s AND note_id=%s",(user_id,note_id))
        if c.fetchone(): c.execute("DELETE FROM bookmarks WHERE user_id=%s AND note_id=%s",(user_id,note_id)); b=False
        else: c.execute("INSERT INTO bookmarks VALUES(%s,%s)",(user_id,note_id)); b=True
    else:
        c.execute("SELECT 1 FROM bookmarks WHERE user_id=? AND note_id=?",(user_id,note_id))
        if c.fetchone(): conn.execute("DELETE FROM bookmarks WHERE user_id=? AND note_id=?",(user_id,note_id)); b=False
        else: conn.execute("INSERT OR IGNORE INTO bookmarks VALUES(?,?)",(user_id,note_id)); b=True
    conn.commit(); conn.close(); return b

def user_bookmarked(user_id, note_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT 1 FROM bookmarks WHERE user_id=%s AND note_id=%s",(user_id,note_id))
    else: c.execute("SELECT 1 FROM bookmarks WHERE user_id=? AND note_id=?",(user_id,note_id))
    row=c.fetchone(); conn.close(); return row is not None

def get_bookmarks(user_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn)
        c.execute("SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id JOIN bookmarks b ON b.note_id=n.id WHERE b.user_id=%s ORDER BY n.created_at DESC",(user_id,))
        rows=c.fetchall()
    else:
        c=conn.cursor()
        c.execute("SELECT n.*, u.username as author_username FROM notes n JOIN users u ON n.user_id=u.id JOIN bookmarks b ON b.note_id=n.id WHERE b.user_id=? ORDER BY n.created_at DESC",(user_id,))
        rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def add_comment(body, user_id, note_id, parent_id=None):
    conn=get_db()
    if _USE_POSTGRES:
        c=conn.cursor(); c.execute("INSERT INTO comments (body,user_id,note_id,parent_id) VALUES (%s,%s,%s,%s) RETURNING id",(body,user_id,note_id,parent_id)); cid=c.fetchone()[0]
    else:
        c=conn.cursor(); c.execute("INSERT INTO comments (body,user_id,note_id,parent_id) VALUES (?,?,?,?)",(body,user_id,note_id,parent_id)); cid=c.lastrowid
    conn.commit(); conn.close(); return cid

def get_comments(note_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT c.*, u.username as author_username FROM comments c JOIN users u ON c.user_id=u.id WHERE c.note_id=%s AND c.parent_id IS NULL ORDER BY c.created_at DESC",(note_id,)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT c.*, u.username as author_username FROM comments c JOIN users u ON c.user_id=u.id WHERE c.note_id=? AND c.parent_id IS NULL ORDER BY c.created_at DESC",(note_id,)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def get_comment_count(note_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT COUNT(*) FROM comments WHERE note_id=%s",(note_id,))
    else: c.execute("SELECT COUNT(*) FROM comments WHERE note_id=?",(note_id,))
    n=c.fetchone()[0]; conn.close(); return n

def get_user_stats(user_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES:
        c.execute("SELECT COUNT(*) FROM notes WHERE user_id=%s",(user_id,)); tn=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(download_count),0) FROM notes WHERE user_id=%s",(user_id,)); td=c.fetchone()[0]
    else:
        c.execute("SELECT COUNT(*) FROM notes WHERE user_id=?",(user_id,)); tn=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(download_count),0) FROM notes WHERE user_id=?",(user_id,)); td=c.fetchone()[0]
    conn.close(); return {'total_notes':tn,'total_downloads':td}
