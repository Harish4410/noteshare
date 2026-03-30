import os
from datetime import timedelta
from flask import Flask, render_template, session, g, request
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

from db.database import init_db
from db.users    import get_user_by_id
from routes      import auth_bp, dashboard_bp, notes_bp, social_bp, chat_bp, admin_bp, study_bp, features_bp

_user_cache = {}

# Simple in-memory rate limiter
_rate_limits = {}

def create_app():
    app = Flask(__name__)
    app.secret_key               = os.environ.get('SECRET_KEY', 'dev-secret')
    # On Render, use persistent disk path if available
    render_uploads = '/opt/render/project/src/uploads'
    if os.path.exists('/opt/render'):
        upload_dir = render_uploads
    else:
        upload_dir = os.path.join(basedir, 'uploads')
    app.config['UPLOAD_FOLDER'] = upload_dir
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()

    @app.before_request
    def load_user():
        if request.path.startswith('/static/'):
            g.user = None; return
        uid = session.get('user_id')
        if not uid:
            g.user = None; return
        cached = _user_cache.get(uid)
        if cached:
            g.user = cached; return
        user = get_user_by_id(uid)
        if not user:
            session.clear(); g.user = None
        else:
            _user_cache[uid] = user
            g.user = user

    @app.context_processor
    def inject_user():
        notif_count = 0
        if g.user and 'poll' not in request.path:
            from db.chat import unread_count as _unread
            notif_count = _unread(g.user['id'])
        return {'current_user': g.user, 'notif_count': notif_count}

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(study_bp)
    app.register_blueprint(features_bp)

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/manifest.json')
    def manifest():
        import json
        from flask import Response
        data = {
            "name": "NoteShare",
            "short_name": "NoteShare",
            "description": "Academic note sharing platform powered by AI",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#6366f1",
            "orientation": "any",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
                {"src": "/static/icons/icon-72.png",  "sizes": "72x72",   "type": "image/png"},
                {"src": "/static/icons/icon-128.png", "sizes": "128x128", "type": "image/png"},
                {"src": "/static/icons/icon-256.png", "sizes": "256x256", "type": "image/png"}
            ],
            "shortcuts": [
                {"name": "Upload Note",  "url": "/notes/upload"},
                {"name": "Browse Notes", "url": "/notes/"},
                {"name": "Chat",         "url": "/chat/"}
            ]
        }
        return Response(
            json.dumps(data),
            mimetype='application/manifest+json',
            headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-cache'}
        )

    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory
        resp = send_from_directory('static', 'sw.js')
        resp.headers['Content-Type'] = 'application/javascript'
        resp.headers['Service-Worker-Allowed'] = '/'
        return resp

    @app.errorhandler(403)
    def forbidden(e):    return render_template('errors/403.html'), 403
    @app.errorhandler(404)
    def not_found(e):    return render_template('errors/404.html'), 404
    @app.errorhandler(500)
    def server_error(e): return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
