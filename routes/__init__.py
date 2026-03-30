from .auth      import auth_bp
from .dashboard import dashboard_bp
from .notes     import notes_bp
from .other     import social_bp, chat_bp, admin_bp, study_bp
from .features  import features_bp

__all__ = ['auth_bp', 'dashboard_bp', 'notes_bp',
           'social_bp', 'chat_bp', 'admin_bp', 'study_bp', 'features_bp']
