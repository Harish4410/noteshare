import os
import uuid
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
from datetime import datetime
import secrets
from datetime import timedelta
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
import psycopg2

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------- DATABASE CONNECTION ----------
def get_db():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Render PostgreSQL
        return psycopg2.connect(database_url)
    else:
        # Local MySQL
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )

# ---------- HELPER ----------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
# ---------- HOME ----------
@app.route("/")
def home():
    return redirect("/login")

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already exists")
            return redirect("/register")

        cursor.execute("INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                       (name, email, password))
        db.commit()
        flash("Registered Successfully")
        return redirect("/login")

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["dark_mode"] = user["dark_mode"]
            return redirect("/dashboard")
        else:
            flash("Invalid credentials")

    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notes WHERE user_id=%s", (session["user_id"],))
    notes = cursor.fetchall()
    return render_template("dashboard.html", notes=notes)

def auto_tag_and_summary(title, subject):
    text = (title + " " + subject).lower()

    keywords = {
        "python": "python",
        "flask": "flask",
        "sql": "database",
        "mysql": "database",
        "ai": "ai",
        "machine learning": "ml",
        "network": "networking",
        "cloud": "cloud",
        "security": "security",
        "data": "data-science"
    }

    tags = []

    for key in keywords:
        if key in text:
            tags.append(keywords[key])

    if not tags:
        tags.append("general")

    summary = f"This note covers {subject} concepts related to {title}. It includes important explanations and academic material."

    return ",".join(tags), summary


# ---------- UPLOAD ----------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        subject = request.form["subject"]
        file = request.files["file"]
        public = 1 if "public" in request.form else 0

        print("Filename:", file.filename)   # 👈 DEBUG LINE 1

        tags, summary = auto_tag_and_summary(title, subject)

        if file and allowed_file(file.filename):
            print("File allowed, inserting into DB")  # 👈 DEBUG LINE 2

            filename = secure_filename(file.filename)
            unique_name = str(uuid.uuid4()) + "_" + filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))

            db = get_db()
            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO notes 
                (title, subject, filename, user_id, is_public, downloads, rating, total_ratings, tags, summary)
                VALUES (%s, %s, %s, %s, %s, 0, 0, 0, %s, %s)
            """, (title, subject, unique_name, session["user_id"], public, tags, summary))

            db.commit()

            flash("Note uploaded successfully")
            return redirect("/dashboard")

        else:
            print("File NOT allowed")  # 👈 Extra safety debug

    return render_template("upload.html")# ---------- DOWNLOAD ----------
@app.route("/download/<filename>")
def download(filename):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE notes SET downloads = downloads + 1 WHERE filename=%s", (filename,))
    db.commit()
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------- PUBLIC NOTES ----------
@app.route("/public")
def public_notes():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT notes.*, users.name,
        (downloads * 2 + rating * 5 + total_ratings * 3) AS trending_score
        FROM notes
        JOIN users ON notes.user_id = users.id
        WHERE is_public=1
        ORDER BY trending_score DESC
    """)

    notes = cursor.fetchall()

    # Attach reviews
    for note in notes:
        cursor.execute("""
            SELECT reviews.review, reviews.created_at, users.name
            FROM reviews
            JOIN users ON reviews.user_id = users.id
            WHERE reviews.note_id=%s
            ORDER BY created_at DESC
        """, (note["id"],))
        note["reviews"] = cursor.fetchall()

    return render_template("public_notes.html", notes=notes)

@app.route("/review/<int:note_id>", methods=["POST"])
def review(note_id):
    if "user_id" not in session:
        return redirect("/login")

    review_text = request.form["review"]

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO reviews (user_id, note_id, review)
        VALUES (%s,%s,%s)
    """, (session["user_id"], note_id, review_text))
    db.commit()

    return redirect("/public")

@app.route("/bookmarks")
def view_bookmarks():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT notes.* 
        FROM bookmarks
        JOIN notes ON bookmarks.note_id = notes.id
        WHERE bookmarks.user_id=%s
    """, (session["user_id"],))

    notes = cursor.fetchall()

    return render_template("bookmarks.html", notes=notes)

@app.route("/bookmark/<int:note_id>")
def bookmark(note_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT IGNORE INTO bookmarks (user_id, note_id)
        VALUES (%s,%s)
    """, (session["user_id"], note_id))

    db.commit()
    return redirect("/public")

@app.route("/remove_bookmark/<int:note_id>")
def remove_bookmark(note_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM bookmarks 
        WHERE user_id=%s AND note_id=%s
    """, (session["user_id"], note_id))

    db.commit()
    return redirect("/bookmarks")

@app.route("/rate/<int:note_id>", methods=["POST"])
def rate(note_id):
    if "user_id" not in session:
        return redirect("/login")

    rating = int(request.form["rating"])

    db = get_db()
    cursor = db.cursor()

    # Insert or update rating
    cursor.execute("""
        INSERT INTO ratings (user_id, note_id, rating)
        VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE rating=%s
    """, (session["user_id"], note_id, rating, rating))

    # Update average rating in notes table
    cursor.execute("""
        SELECT AVG(rating), COUNT(*) FROM ratings WHERE note_id=%s
    """, (note_id,))
    avg, total = cursor.fetchone()

    cursor.execute("""
        UPDATE notes SET rating=%s, total_ratings=%s WHERE id=%s
    """, (avg, total, note_id))

    db.commit()
    return redirect("/public")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- ADMIN ----------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["admin"] = True
            return redirect("/admin/dashboard")

    return render_template("admin.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM notes")
    notes = cursor.fetchone()[0]

    return render_template("admin.html", users=users, notes=notes)

@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    # Total notes
    cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id=%s", (session["user_id"],))
    total_notes = cursor.fetchone()[0]

    # Total downloads
    cursor.execute("SELECT SUM(downloads) FROM notes WHERE user_id=%s", (session["user_id"],))
    total_downloads = cursor.fetchone()[0] or 0

    # Notes per subject
    cursor.execute("""
        SELECT subject, COUNT(*) 
        FROM notes 
        WHERE user_id=%s
        GROUP BY subject
    """, (session["user_id"],))

    subject_data = cursor.fetchall()

    subjects = [row[0] for row in subject_data]
    counts = [row[1] for row in subject_data]

    return render_template("analytics.html",
                           total_notes=total_notes,
                           total_downloads=total_downloads,
                           subjects=subjects,
                           counts=counts)

@app.route("/groups")
def groups():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM groups")
    groups = cursor.fetchall()

    return render_template("groups.html", groups=groups)

@app.route("/create_group", methods=["POST"])
def create_group():
    if "user_id" not in session:
        return redirect("/login")

    name = request.form["name"]

    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO groups (name) VALUES (%s)", (name,))
    db.commit()

    return redirect("/groups")

@app.route("/chat/<int:group_id>")
def chat(group_id):
    if "user_id" not in session:
        return redirect("/login")

    return render_template("chat.html", group_id=group_id)

@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(minutes=15)

            cursor.execute("""
                UPDATE users 
                SET reset_token=%s, reset_expiry=%s 
                WHERE email=%s
            """, (token, expiry, email))
            db.commit()

            reset_link = url_for("reset_password", token=token, _external=True)

            # For now, print in terminal (later you can send email)
            print("RESET LINK:", reset_link)

            flash("Reset link generated. Check terminal.")
        else:
            flash("Email not found.")

    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM users 
        WHERE reset_token=%s AND reset_expiry > %s
    """, (token, datetime.now()))

    user = cursor.fetchone()

    if not user:
        return "Invalid or expired token"

    if request.method == "POST":
        new_password = generate_password_hash(request.form["password"])

        cursor.execute("""
            UPDATE users 
            SET password=%s, reset_token=NULL, reset_expiry=NULL
            WHERE id=%s
        """, (new_password, user["id"]))
        db.commit()

        flash("Password updated successfully.")
        return redirect("/login")

    return render_template("reset.html")

@app.route("/toggle_dark")
def toggle_dark():
    if "user_id" not in session:
        return redirect("/login")

    new_mode = 0 if session.get("dark_mode") else 1

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE users SET dark_mode=%s WHERE id=%s
    """, (new_mode, session["user_id"]))
    db.commit()

    session["dark_mode"] = new_mode

    return redirect(request.referrer or "/dashboard")

if __name__ == "__main__":
    app.run(debug=True)