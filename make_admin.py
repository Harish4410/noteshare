"""
Run this AFTER registering your account:
  python make_admin.py
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from db.database import get_db, dict_cursor, _USE_POSTGRES

conn = get_db()
print(f"\n[Using {'PostgreSQL/Neon' if _USE_POSTGRES else 'SQLite'}]\n")

if _USE_POSTGRES:
    c = dict_cursor(conn)
    c.execute("SELECT id, username, email, role FROM users ORDER BY id")
    users = c.fetchall()
else:
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users ORDER BY id")
    users = [{'id':r[0],'username':r[1],'email':r[2],'role':r[3]} for r in c.fetchall()]

if not users:
    print("No users found!")
    print("Please register at http://localhost:5000/auth/register first.\n")
    conn.close()
    exit()

print("All registered users:")
print("-" * 50)
for u in users:
    print(f"  [{u['id']}] {u['username']} ({u['email']}) — role: {u['role']}")
print("-" * 50)

username = input("\nEnter username to make admin: ").strip()

if _USE_POSTGRES:
    c = conn.cursor()
    c.execute("UPDATE users SET role='admin' WHERE username=%s", (username,))
else:
    conn.execute("UPDATE users SET role='admin' WHERE username=?", (username,))

conn.commit()
conn.close()
print(f"\n✅ Done! '{username}' is now admin.")
print("Restart app.py and log in — Admin Panel will appear in sidebar.\n")
