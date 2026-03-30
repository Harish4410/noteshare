# 📚 NoteShare — AI-Powered Academic Platform

> A full-stack academic web application for sharing, discovering, and learning from notes — powered by Google Gemini AI.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-green?logo=flask)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange)
![Gemini AI](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-purple?logo=google)
![Bootstrap](https://img.shields.io/badge/UI-Bootstrap%205-blue?logo=bootstrap)

---

## 🚀 Live Demo
> Run locally at `http://localhost:5000`

**Admin Login:**
- Email: `lakshmisundar4410@gmail.com`
- Password: `Harish@4410`

---

## ✨ Features

### 📄 Notes System
- Upload PDF, DOCX, PPTX, TXT files (max 16MB)
- Browse with advanced filters (subject, file type, sort by popularity/views)
- PDF preview inside browser (no download needed)
- Like, bookmark, comment on notes
- Infinite scroll pagination
- Personalized recommendations

### 🤖 AI Features (Google Gemini 1.5 Flash — FREE)
- **Auto Summary** — 5 bullet point summary
- **Flashcards** — 8 Q&A flashcard set
- **Quiz** — 5 multiple choice questions
- **Quality Score** — 0-10 rating
- **Improve Note** — AI restructures and improves
- **Missing Topics** — suggests what's missing
- **Ask AI About Note** — chat with context from your note
- **Exam Mode** — timed 5-minute quiz

### 💬 Chat System (WhatsApp-style)
- Group chat rooms
- Private direct messages
- Long-polling real-time updates (4s interval)
- Emoji picker, message history

### 👥 Social Features
- Follow / Unfollow users
- Activity feed (followed users' notes)
- Real-time notifications (like, comment, follow, admin)
- User profiles with stats

### 🏆 Gamification
- XP points system
- 8 achievement badges
- Level progression
- Platform leaderboard

### 📊 Analytics Dashboard
- Views chart (last 7 days) — Chart.js
- Subject distribution doughnut chart
- Trending notes platform-wide
- Per-note stats (views, downloads, likes)

### 🛡️ Admin Panel
- Manage users (ban/unban/promote/delete)
- Approve/reject notes
- Monitor chat groups
- Platform-wide stats

### 📅 Study Planner
- Kanban board (Todo / Doing / Done)
- Task priorities and due dates
- AJAX status transitions

### 📚 Course-wise Notes
- Notes organized by subject
- Browse by course/subject category

### 📱 Production UI/UX
- **Dark Mode** (Ctrl+D)
- **Command Palette** (Ctrl+K) — VS Code style
- **PWA** — installable as mobile/desktop app
- **Skeleton Loading** animations
- **Drag & Drop** file upload
- **Voice Search** (Web Speech API)
- **Text-to-Speech** — read notes aloud
- **Infinite Scroll** pagination
- **Responsive** — mobile-first with bottom nav
- **Micro-interactions** — ripple effects, animations

### 🔐 Security
- Password hashing (Werkzeug PBKDF2-SHA256)
- Session-based authentication (7-day persistence)
- Rate limiting on login (10 attempts/min per IP)
- File type and size validation
- Secure filename handling
- HTTP security headers (X-Frame-Options, X-XSS-Protection)
- Role-based access control (user/admin)
- Input validation and sanitization

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Flask 3.0.3 |
| Database | SQLite 3 (14 tables, 7 indexes) |
| AI | Google Gemini 1.5 Flash (free) |
| Frontend | Bootstrap 5.3, Chart.js, Vanilla JS |
| Auth | Session-based with Werkzeug |
| File Processing | PyPDF2, python-docx, python-pptx |
| Deployment | Gunicorn, Render/Railway ready |

---

## 📁 Project Structure

```
noteshare/
├── app.py                 # Flask app factory
├── .env                   # Configuration
├── requirements.txt
├── db/
│   ├── database.py        # SQLite engine + 14 tables
│   ├── users.py           # User CRUD + auth
│   ├── notes.py           # Notes + likes + bookmarks
│   └── chat.py            # Chat + notifications + tasks
├── routes/
│   ├── auth.py            # Login, register, reset
│   ├── dashboard.py       # Dashboard + profile
│   ├── notes.py           # Upload, view, AI tools
│   ├── other.py           # Chat, social, admin, study
│   └── features.py        # AI chat, analytics, gamification
├── utils/
│   ├── ai_utils.py        # Gemini AI integration
│   └── auth.py            # Auth decorators
├── templates/             # 29 Jinja2 templates
├── static/
│   ├── css/
│   │   ├── design-system.css  # 1,157 lines design system
│   │   └── app.css
│   ├── js/app.js          # 455 lines vanilla JS
│   └── sw.js              # Service Worker (PWA)
└── uploads/               # Uploaded files
```

---

## ⚙️ Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/noteshare.git
cd noteshare

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Edit .env — add your GEMINI_API_KEY

# 5. Run
python app.py
```

Open `http://localhost:5000`

---

## 🔑 Environment Variables (.env)

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=                          # Empty = SQLite (recommended)
GEMINI_API_KEY=your-gemini-key-here    # Get free at aistudio.google.com
```

---

## 📊 Stats

| Metric | Value |
|--------|-------|
| Lines of Code | 7,400+ |
| API Routes | 62 |
| Database Tables | 14 |
| HTML Templates | 29 |
| Python Files | 10 |

---

## 📸 Screenshots

> Login → Dashboard → Upload Note → Note View + AI → Chat → Admin Panel

---

## 👤 Author

**Lakshmi Sundar (Harish)**
- Email: lakshmisundar4410@gmail.com
- Project: NoteShare — AI-Powered Academic Platform

---

## 📄 License

MIT License — free to use and modify.
