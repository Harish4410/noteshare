"""db/chat.py – Works with both PostgreSQL and SQLite."""
from .database import get_db, dict_cursor, _USE_POSTGRES

def _fmt(row):
    d = dict(row)
    if d.get('created_at'):
        d['created_at'] = str(d['created_at'])[:19].replace('T', ' ')
    return d

def _get_username(uid):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT username FROM users WHERE id=%s",(uid,))
    else: c.execute("SELECT username FROM users WHERE id=?",(uid,))
    row=c.fetchone(); conn.close()
    return (row[0] if row else 'Unknown')

def create_group(name, description, creator_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=conn.cursor(); c.execute("INSERT INTO chat_groups (name,description,creator_id) VALUES (%s,%s,%s) RETURNING id",(name,description,creator_id)); gid=c.fetchone()[0]
        c.execute("INSERT INTO group_members (group_id,user_id) VALUES (%s,%s)",(gid,creator_id))
    else:
        c=conn.cursor(); c.execute("INSERT INTO chat_groups (name,description,creator_id) VALUES (?,?,?)",(name,description,creator_id)); gid=c.lastrowid
        c.execute("INSERT OR IGNORE INTO group_members (group_id,user_id) VALUES (?,?)",(gid,creator_id))
    conn.commit(); conn.close(); return gid

def get_all_groups():
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn)
        c.execute("SELECT g.*,u.username as creator_username,(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id=g.id) as member_count FROM chat_groups g JOIN users u ON g.creator_id=u.id ORDER BY g.created_at DESC LIMIT 50")
        rows=c.fetchall()
    else:
        c=conn.cursor()
        c.execute("SELECT g.*,u.username as creator_username,(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id=g.id) as member_count FROM chat_groups g JOIN users u ON g.creator_id=u.id ORDER BY g.created_at DESC LIMIT 50")
        rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def get_group(group_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT g.*,u.username as creator_username,(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id=g.id) as member_count FROM chat_groups g JOIN users u ON g.creator_id=u.id WHERE g.id=%s",(group_id,)); row=c.fetchone()
    else:
        c=conn.cursor(); c.execute("SELECT g.*,u.username as creator_username,(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id=g.id) as member_count FROM chat_groups g JOIN users u ON g.creator_id=u.id WHERE g.id=?",(group_id,)); row=c.fetchone()
    conn.close(); return dict(row) if row else None

def join_group(group_id, user_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("INSERT INTO group_members VALUES(%s,%s) ON CONFLICT DO NOTHING",(group_id,user_id))
    else: conn.execute("INSERT OR IGNORE INTO group_members VALUES(?,?)",(group_id,user_id))
    conn.commit(); conn.close()

def is_member(group_id, user_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT 1 FROM group_members WHERE group_id=%s AND user_id=%s",(group_id,user_id))
    else: c.execute("SELECT 1 FROM group_members WHERE group_id=? AND user_id=?",(group_id,user_id))
    row=c.fetchone(); conn.close(); return row is not None

def get_group_members(group_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT u.* FROM users u JOIN group_members gm ON u.id=gm.user_id WHERE gm.group_id=%s",(group_id,)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT u.* FROM users u JOIN group_members gm ON u.id=gm.user_id WHERE gm.group_id=?",(group_id,)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def delete_group(group_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("DELETE FROM chat_groups WHERE id=%s",(group_id,))
    else: conn.execute("DELETE FROM chat_groups WHERE id=?",(group_id,))
    conn.commit(); conn.close()

def send_group_message(body, sender_id, group_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=conn.cursor(); c.execute("INSERT INTO messages (body,sender_id,group_id) VALUES (%s,%s,%s) RETURNING id,created_at",(body,sender_id,group_id)); row=c.fetchone()
        msg_id=row[0]; created=str(row[1])[:19].replace('T',' ')
    else:
        c=conn.cursor(); c.execute("INSERT INTO messages (body,sender_id,group_id) VALUES (?,?,?)",(body,sender_id,group_id))
        msg_id=c.lastrowid
        c.execute("SELECT created_at FROM messages WHERE id=?",(msg_id,)); created=str(c.fetchone()[0])[:19]
    conn.commit(); conn.close()
    return {'id':msg_id,'body':body,'sender_id':sender_id,'group_id':group_id,'receiver_id':None,'created_at':created,'sender_username':_get_username(sender_id)}

def send_private_message(body, sender_id, receiver_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=conn.cursor(); c.execute("INSERT INTO messages (body,sender_id,receiver_id) VALUES (%s,%s,%s) RETURNING id,created_at",(body,sender_id,receiver_id)); row=c.fetchone()
        msg_id=row[0]; created=str(row[1])[:19].replace('T',' ')
    else:
        c=conn.cursor(); c.execute("INSERT INTO messages (body,sender_id,receiver_id) VALUES (?,?,?)",(body,sender_id,receiver_id))
        msg_id=c.lastrowid
        c.execute("SELECT created_at FROM messages WHERE id=?",(msg_id,)); created=str(c.fetchone()[0])[:19]
    conn.commit(); conn.close()
    return {'id':msg_id,'body':body,'sender_id':sender_id,'group_id':None,'receiver_id':receiver_id,'created_at':created,'sender_username':_get_username(sender_id)}

def get_group_messages(group_id, limit=100):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id=%s AND m.is_deleted=0 ORDER BY m.created_at ASC LIMIT %s",(group_id,limit)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id=? AND m.is_deleted=0 ORDER BY m.created_at ASC LIMIT ?",(group_id,limit)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return [_fmt(r) for r in rows]

def get_new_group_messages(group_id, after_id=0):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id=%s AND m.is_deleted=0 AND m.id>%s ORDER BY m.created_at ASC",(group_id,after_id)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id=? AND m.is_deleted=0 AND m.id>? ORDER BY m.created_at ASC",(group_id,after_id)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return [_fmt(r) for r in rows]

def get_private_messages(user_a, user_b):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id IS NULL AND m.is_deleted=0 AND ((m.sender_id=%s AND m.receiver_id=%s) OR (m.sender_id=%s AND m.receiver_id=%s)) ORDER BY m.created_at ASC LIMIT 100",(user_a,user_b,user_b,user_a)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id IS NULL AND m.is_deleted=0 AND ((m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)) ORDER BY m.created_at ASC LIMIT 100",(user_a,user_b,user_b,user_a)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return [_fmt(r) for r in rows]

def get_new_private_messages(user_a, user_b, after_id=0):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id IS NULL AND m.is_deleted=0 AND m.id>%s AND ((m.sender_id=%s AND m.receiver_id=%s) OR (m.sender_id=%s AND m.receiver_id=%s)) ORDER BY m.created_at ASC",(after_id,user_a,user_b,user_b,user_a)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT m.*,u.username as sender_username FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.group_id IS NULL AND m.is_deleted=0 AND m.id>? AND ((m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)) ORDER BY m.created_at ASC",(after_id,user_a,user_b,user_b,user_a)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return [_fmt(r) for r in rows]

def get_dm_contacts(user_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT DISTINCT u.* FROM users u JOIN messages m ON (m.sender_id=u.id OR m.receiver_id=u.id) WHERE m.group_id IS NULL AND (m.sender_id=%s OR m.receiver_id=%s) AND u.id!=%s",(user_id,user_id,user_id)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT DISTINCT u.* FROM users u JOIN messages m ON (m.sender_id=u.id OR m.receiver_id=u.id) WHERE m.group_id IS NULL AND (m.sender_id=? OR m.receiver_id=?) AND u.id!=?",(user_id,user_id,user_id)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def delete_message(msg_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("UPDATE messages SET is_deleted=1 WHERE id=%s",(msg_id,))
    else: conn.execute("UPDATE messages SET is_deleted=1 WHERE id=?",(msg_id,))
    conn.commit(); conn.close()

def create_task(title, description, priority, due_date, user_id):
    conn=get_db()
    if _USE_POSTGRES:
        c=conn.cursor(); c.execute("INSERT INTO tasks (title,description,priority,due_date,user_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",(title,description,priority,due_date,user_id)); tid=c.fetchone()[0]
    else:
        c=conn.cursor(); c.execute("INSERT INTO tasks (title,description,priority,due_date,user_id) VALUES (?,?,?,?,?)",(title,description,priority,due_date,user_id)); tid=c.lastrowid
    conn.commit(); conn.close(); return tid

def get_tasks_by_status(user_id, status):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT * FROM tasks WHERE user_id=%s AND status=%s ORDER BY due_date ASC NULLS LAST",(user_id,status)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT * FROM tasks WHERE user_id=? AND status=? ORDER BY due_date ASC",(user_id,status)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def update_task_status(task_id, status, user_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("UPDATE tasks SET status=%s WHERE id=%s AND user_id=%s",(status,task_id,user_id))
    else: conn.execute("UPDATE tasks SET status=? WHERE id=? AND user_id=?",(status,task_id,user_id))
    conn.commit(); conn.close()

def delete_task(task_id, user_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("DELETE FROM tasks WHERE id=%s AND user_id=%s",(task_id,user_id))
    else: conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?",(task_id,user_id))
    conn.commit(); conn.close()

def create_study_plan(title, content, user_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("INSERT INTO study_plans (title,content,user_id) VALUES (%s,%s,%s)",(title,content,user_id))
    else: conn.execute("INSERT INTO study_plans (title,content,user_id) VALUES (?,?,?)",(title,content,user_id))
    conn.commit(); conn.close()

def get_study_plans(user_id, limit=5):
    conn=get_db()
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute("SELECT * FROM study_plans WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",(user_id,limit)); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute("SELECT * FROM study_plans WHERE user_id=? ORDER BY created_at DESC LIMIT ?",(user_id,limit)); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def add_notification(user_id, actor_id, ntype, message, link=None):
    if user_id==actor_id: return
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("INSERT INTO notifications (user_id,actor_id,type,message,link) VALUES (%s,%s,%s,%s,%s)",(user_id,actor_id,ntype,message,link))
    else: conn.execute("INSERT INTO notifications (user_id,actor_id,type,message,link) VALUES (?,?,?,?,?)",(user_id,actor_id,ntype,message,link))
    conn.commit(); conn.close()

def get_notifications(user_id, unread_only=False, limit=20):
    conn=get_db()
    where="n.user_id=%s" if _USE_POSTGRES else "n.user_id=?"
    params=[user_id]
    if unread_only: where+=(" AND n.is_read=0")
    if _USE_POSTGRES:
        c=dict_cursor(conn); c.execute(f"SELECT n.*,u.username as actor_username FROM notifications n LEFT JOIN users u ON n.actor_id=u.id WHERE {where} ORDER BY n.created_at DESC LIMIT %s",params+[limit]); rows=c.fetchall()
    else:
        c=conn.cursor(); c.execute(f"SELECT n.*,u.username as actor_username FROM notifications n LEFT JOIN users u ON n.actor_id=u.id WHERE {where} ORDER BY n.created_at DESC LIMIT ?",params+[limit]); rows=[dict(r) for r in c.fetchall()]
    conn.close(); return rows

def mark_all_read(user_id):
    conn=get_db()
    if _USE_POSTGRES: conn.cursor().execute("UPDATE notifications SET is_read=1 WHERE user_id=%s",(user_id,))
    else: conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(user_id,))
    conn.commit(); conn.close()

def unread_count(user_id):
    conn=get_db(); c=conn.cursor()
    if _USE_POSTGRES: c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",(user_id,))
    else: c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",(user_id,))
    n=c.fetchone()[0]; conn.close(); return n
