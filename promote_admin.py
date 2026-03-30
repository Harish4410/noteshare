"""
Run once to promote lakshmisundar4410@gmail.com to admin.
python promote_admin.py
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from db.database import _USE_POSTGRES, get_db

ADMIN_EMAIL = 'lakshmisundar4410@gmail.com'

conn = get_db()
print(f"[Using {'PostgreSQL' if _USE_POSTGRES else 'SQLite'}]")

if _USE_POSTGRES:
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users WHERE email=%s", (ADMIN_EMAIL,))
else:
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users WHERE email=?", (ADMIN_EMAIL,))

user = c.fetchone()

if not user:
    print(f"\n❌ No user found with email: {ADMIN_EMAIL}")
    print("Please register first at http://localhost:5000/auth/register")
else:
    uid = user[0]
    if _USE_POSTGRES:
        conn.cursor().execute("UPDATE users SET role='admin' WHERE id=%s", (uid,))
    else:
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (uid,))
    conn.commit()
    print(f"\n✅ {user[1]} ({ADMIN_EMAIL}) is now ADMIN!")
    print("Restart the app and log in — Admin Panel will appear in sidebar.")

conn.close()
