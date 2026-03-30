"""db/users.py – Works with both PostgreSQL and SQLite."""
from .database import get_db, dict_cursor, _USE_POSTGRES
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

def _q(sql):
    """Use %s for postgres, ? for sqlite."""
    if _USE_POSTGRES:
        return sql
    return sql.replace('%s', '?').replace(' ILIKE ', ' LIKE ').replace('ON CONFLICT DO NOTHING', '').replace('NOW()', "datetime('now')")

def _fetchone(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchone()

def _fetchall(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchall()

def _execute(conn, sql, params=()):
    sql = _q(sql)
    c = conn.cursor()
    c.execute(sql, params)
    return c

def create_user(username, email, password):
    conn = get_db()
    try:
        ph = generate_password_hash(password)
        if _USE_POSTGRES:
            c = dict_cursor(conn)
            c.execute("INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s) RETURNING *",
                      (username, email, ph))
            row = c.fetchone()
        else:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                      (username, email, ph))
            uid = c.lastrowid
            row = None
        conn.commit()
        return get_user_by_email(email)
    except Exception as e:
        conn.rollback(); raise e
    finally:
        conn.close()

def get_user_by_id(uid):
    conn = get_db()
    row  = _fetchone(conn, "SELECT * FROM users WHERE id=%s" if _USE_POSTGRES else "SELECT * FROM users WHERE id=?", (uid,))
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email):
    conn = get_db()
    sql  = "SELECT * FROM users WHERE email=%s" if _USE_POSTGRES else "SELECT * FROM users WHERE email=?"
    row  = _fetchone(conn, sql, (email.lower(),))
    conn.close()
    return dict(row) if row else None

def get_user_by_username(username):
    conn = get_db()
    sql  = "SELECT * FROM users WHERE username=%s" if _USE_POSTGRES else "SELECT * FROM users WHERE username=?"
    row  = _fetchone(conn, sql, (username,))
    conn.close()
    return dict(row) if row else None

def get_user_by_identifier(identifier):
    conn = get_db()
    if _USE_POSTGRES:
        sql = "SELECT * FROM users WHERE email=%s OR username=%s"
    else:
        sql = "SELECT * FROM users WHERE email=? OR username=?"
    row = _fetchone(conn, sql, (identifier.lower(), identifier))
    conn.close()
    return dict(row) if row else None

def verify_password(user, password):
    return check_password_hash(user['password_hash'], password)

def update_last_seen(uid):
    conn = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute("UPDATE users SET last_seen=NOW() WHERE id=%s", (uid,))
    else:
        conn.execute("UPDATE users SET last_seen=datetime('now') WHERE id=?", (uid,))
    conn.commit(); conn.close()

def set_reset_token(email):
    token = secrets.token_urlsafe(32)
    conn  = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute("UPDATE users SET reset_token=%s WHERE email=%s", (token, email))
    else:
        conn.execute("UPDATE users SET reset_token=? WHERE email=?", (token, email))
    conn.commit(); conn.close()
    return token

def reset_password(token, new_password):
    conn = get_db()
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute("SELECT * FROM users WHERE reset_token=%s", (token,))
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE reset_token=?", (token,))
    row = c.fetchone()
    if not row:
        conn.close(); return False
    uid = row['id'] if isinstance(row, dict) else row[0]
    if _USE_POSTGRES:
        conn.cursor().execute("UPDATE users SET password_hash=%s, reset_token=NULL WHERE id=%s",
                              (generate_password_hash(new_password), uid))
    else:
        conn.execute("UPDATE users SET password_hash=?, reset_token=NULL WHERE id=?",
                     (generate_password_hash(new_password), uid))
    conn.commit(); conn.close()
    return True

def update_user_field(uid, field, value):
    allowed = {'bio', 'role', 'is_banned'}
    if field not in allowed: return
    conn = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute(f"UPDATE users SET {field}=%s WHERE id=%s", (value, uid))
    else:
        conn.execute(f"UPDATE users SET {field}=? WHERE id=?", (value, uid))
    conn.commit(); conn.close()

def delete_user(uid):
    conn = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute("DELETE FROM users WHERE id=%s", (uid,))
    else:
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()

def get_all_users(search='', page=1, per_page=20):
    conn   = get_db()
    offset = (page - 1) * per_page
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        if search:
            like = f'%{search}%'
            c.execute("SELECT * FROM users WHERE username ILIKE %s OR email ILIKE %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                      (like, like, per_page, offset))
            rows = c.fetchall()
            c.execute("SELECT COUNT(*) as n FROM users WHERE username ILIKE %s OR email ILIKE %s", (like, like))
            total = c.fetchone()['n']
        else:
            c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s", (per_page, offset))
            rows = c.fetchall()
            c.execute("SELECT COUNT(*) as n FROM users")
            total = c.fetchone()['n']
    else:
        import sqlite3
        c = conn.cursor()
        if search:
            like = f'%{search}%'
            c.execute("SELECT * FROM users WHERE username LIKE ? OR email LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                      (like, like, per_page, offset))
            rows = [dict(r) for r in c.fetchall()]
            c.execute("SELECT COUNT(*) FROM users WHERE username LIKE ? OR email LIKE ?", (like, like))
            total = c.fetchone()[0]
        else:
            c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (per_page, offset))
            rows = [dict(r) for r in c.fetchall()]
            c.execute("SELECT COUNT(*) FROM users")
            total = c.fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total

def follow_user(follower_id, followed_id):
    conn = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute("INSERT INTO follows (follower_id, followed_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                              (follower_id, followed_id))
    else:
        conn.execute("INSERT OR IGNORE INTO follows (follower_id, followed_id) VALUES (?,?)",
                     (follower_id, followed_id))
    conn.commit(); conn.close()

def unfollow_user(follower_id, followed_id):
    conn = get_db()
    if _USE_POSTGRES:
        conn.cursor().execute("DELETE FROM follows WHERE follower_id=%s AND followed_id=%s", (follower_id, followed_id))
    else:
        conn.execute("DELETE FROM follows WHERE follower_id=? AND followed_id=?", (follower_id, followed_id))
    conn.commit(); conn.close()

def is_following(follower_id, followed_id):
    conn = get_db()
    if _USE_POSTGRES:
        c = conn.cursor()
        c.execute("SELECT 1 FROM follows WHERE follower_id=%s AND followed_id=%s", (follower_id, followed_id))
    else:
        c = conn.cursor()
        c.execute("SELECT 1 FROM follows WHERE follower_id=? AND followed_id=?", (follower_id, followed_id))
    row = c.fetchone(); conn.close()
    return row is not None

def get_follower_count(uid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM follows WHERE followed_id=%s" if _USE_POSTGRES else "SELECT COUNT(*) FROM follows WHERE followed_id=?", (uid,))
    n = c.fetchone()[0]; conn.close(); return n

def get_following_count(uid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM follows WHERE follower_id=%s" if _USE_POSTGRES else "SELECT COUNT(*) FROM follows WHERE follower_id=?", (uid,))
    n = c.fetchone()[0]; conn.close(); return n

def get_followers(uid):
    conn = get_db()
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute("SELECT u.* FROM users u JOIN follows f ON u.id=f.follower_id WHERE f.followed_id=%s", (uid,))
        rows = c.fetchall()
    else:
        c = conn.cursor()
        c.execute("SELECT u.* FROM users u JOIN follows f ON u.id=f.follower_id WHERE f.followed_id=?", (uid,))
        rows = [dict(r) for r in c.fetchall()]
    conn.close(); return rows

def get_following(uid):
    conn = get_db()
    if _USE_POSTGRES:
        c = dict_cursor(conn)
        c.execute("SELECT u.* FROM users u JOIN follows f ON u.id=f.followed_id WHERE f.follower_id=%s", (uid,))
        rows = c.fetchall()
    else:
        c = conn.cursor()
        c.execute("SELECT u.* FROM users u JOIN follows f ON u.id=f.followed_id WHERE f.follower_id=?", (uid,))
        rows = [dict(r) for r in c.fetchall()]
    conn.close(); return rows

def get_followed_ids(uid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT followed_id FROM follows WHERE follower_id=%s" if _USE_POSTGRES else "SELECT followed_id FROM follows WHERE follower_id=?", (uid,))
    rows = c.fetchall(); conn.close()
    return [r[0] for r in rows]
