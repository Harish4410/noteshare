"""
db/database.py - SQLite only, fast, no cloud needed.
"""
import os, sqlite3
from dotenv import load_dotenv

basedir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

_USE_POSTGRES = False   # Always SQLite
SQLITE_PATH   = os.path.join(basedir, 'noteshare.db')

def get_db():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn

def dict_cursor(conn):
    return _SqDictCursor(conn)

class _SqDictCursor:
    def __init__(self, conn):
        self._c = conn.cursor(); self._last = None
    def execute(self, sql, p=()):
        sql = sql.replace('%s','?').replace(' ILIKE ',' LIKE ')
        self._last = None
        if 'RETURNING' in sql.upper():
            idx = sql.upper().index('RETURNING')
            col = sql[idx+9:].strip().split()[0].strip(')').lower()
            sql = sql[:idx].rstrip()
            if not sql.endswith(')'): sql += ')'
            self._c.execute(sql, p)
            self._last = {'id': self._c.lastrowid, col: self._c.lastrowid}
        else:
            self._c.execute(sql, p)
    def fetchone(self):
        if self._last is not None:
            r=self._last; self._last=None; return r
        r=self._c.fetchone(); return dict(r) if r else None
    def fetchall(self): return [dict(r) for r in self._c.fetchall()]
    @property
    def lastrowid(self): return self._c.lastrowid

def _ddl(sql):
    import re
    sql = sql.replace('SERIAL PRIMARY KEY','INTEGER PRIMARY KEY AUTOINCREMENT')
    sql = sql.replace('TIMESTAMP DEFAULT NOW()',"TEXT DEFAULT (datetime('now'))")
    sql = sql.replace('NOW()',"datetime('now')")
    sql = re.sub(r'REFERENCES\s+\w+\(\w+\)(\s+ON DELETE \w+)?','',sql)
    return sql

def init_db():
    conn = get_db()
    for s in _tables():
        conn.execute(_ddl(s))
    conn.commit()
    # Indexes for speed
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_notes_user    ON notes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_notes_public  ON notes(is_public,is_approved)",
        "CREATE INDEX IF NOT EXISTS idx_messages_grp  ON messages(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_dm   ON messages(sender_id,receiver_id)",
        "CREATE INDEX IF NOT EXISTS idx_notifs_user   ON notifications(user_id,is_read)",
        "CREATE INDEX IF NOT EXISTS idx_follows       ON follows(follower_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_user    ON tasks(user_id,status)",
    ]:
        try: conn.execute(idx)
        except: pass
    conn.commit()
    _seed_admin(conn)
    conn.close()
    print("[DB] SQLite ready.")

def _seed_admin(conn):
    """Create admin account if it doesn't exist."""
    from werkzeug.security import generate_password_hash
    ADMIN_EMAIL    = 'lakshmisundar4410@gmail.com'
    ADMIN_USERNAME = 'Harish'
    ADMIN_PASSWORD = 'Harish@4410'   # default password — change after first login

    row = conn.execute("SELECT id FROM users WHERE email=?", (ADMIN_EMAIL,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            (ADMIN_USERNAME, ADMIN_EMAIL,
             generate_password_hash(ADMIN_PASSWORD), 'admin')
        )
        conn.commit()
        print(f"[DB] ✅ Admin account created: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    else:
        # Make sure existing account has admin role
        conn.execute("UPDATE users SET role='admin' WHERE email=?", (ADMIN_EMAIL,))
        conn.commit()
        print(f"[DB] ✅ Admin account verified: {ADMIN_USERNAME}")

def _tables():
    return [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            bio TEXT DEFAULT '', role TEXT DEFAULT 'user',
            is_banned INTEGER DEFAULT 0, reset_token TEXT,
            created_at TIMESTAMP DEFAULT NOW(), last_seen TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            description TEXT DEFAULT '', subject TEXT DEFAULT '',
            file_path TEXT NOT NULL, file_type TEXT DEFAULT 'pdf',
            user_id INTEGER NOT NULL, is_approved INTEGER DEFAULT 1,
            is_public INTEGER DEFAULT 1, download_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0, ai_score REAL,
            ai_summary TEXT, ai_flashcards TEXT, ai_quiz TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS note_likes (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL,
            note_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, note_id))""",
        """CREATE TABLE IF NOT EXISTS bookmarks (
            user_id INTEGER NOT NULL, note_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, note_id))""",
        """CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY, body TEXT NOT NULL,
            user_id INTEGER NOT NULL, note_id INTEGER NOT NULL,
            parent_id INTEGER, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS collections (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            description TEXT DEFAULT '', user_id INTEGER NOT NULL,
            is_public INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS collection_notes (
            collection_id INTEGER NOT NULL, note_id INTEGER NOT NULL,
            PRIMARY KEY(collection_id, note_id))""",
        """CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER NOT NULL, followed_id INTEGER NOT NULL,
            PRIMARY KEY(follower_id, followed_id))""",
        """CREATE TABLE IF NOT EXISTS chat_groups (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            description TEXT DEFAULT '', creator_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            PRIMARY KEY(group_id, user_id))""",
        """CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY, body TEXT, msg_type TEXT DEFAULT 'text',
            sender_id INTEGER NOT NULL, group_id INTEGER, receiver_id INTEGER,
            is_pinned INTEGER DEFAULT 0, is_starred INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            description TEXT DEFAULT '', status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium', due_date TEXT,
            user_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS study_plans (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            content TEXT NOT NULL, user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL,
            actor_id INTEGER, type TEXT NOT NULL, message TEXT NOT NULL,
            link TEXT, is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW())""",
    ]
