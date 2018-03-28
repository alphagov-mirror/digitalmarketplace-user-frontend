import os
import jinja2
from dmutils.status import get_version_label
from dmutils.asset_fingerprint import AssetFingerprinter

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):

    VERSION = get_version_label(
        os.path.abspath(os.path.dirname(__file__))
    )
    SESSION_COOKIE_NAME = 'dm_session'
    SESSION_COOKIE_PATH = '/'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True

    PERMANENT_SESSION_LIFETIME = 4 * 3600

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    DM_DATA_API_URL = None
    DM_DATA_API_AUTH_TOKEN = None
    DM_NOTIFY_API_KEY = None

    NOTIFY_TEMPLATES = {
        'reset_password': '7501026e-d0ba-4cd1-b64f-6a19e1f0913f',
    }

    DEBUG = False

    SECRET_KEY = None
    SHARED_EMAIL_KEY = None
    RESET_PASSWORD_SALT = 'ResetPasswordSalt'
    INVITE_EMAIL_SALT = 'InviteEmailSalt'

    STATIC_URL_PATH = '/user/static'
    ASSET_PATH = STATIC_URL_PATH + '/'
    BASE_TEMPLATE_DATA = {
        'header_class': 'with-proposition',
        'asset_path': ASSET_PATH,
        'asset_fingerprinter': AssetFingerprinter(asset_root=ASSET_PATH)
    }

    # Feature Flags
    RAISE_ERROR_ON_MISSING_FEATURES = True

    # LOGGING
    DM_LOG_LEVEL = 'DEBUG'
    DM_PLAIN_TEXT_LOGS = False
    DM_LOG_PATH = None
    DM_APP_NAME = 'user-frontend'

    @staticmethod
    def init_app(app):
        repo_root = os.path.abspath(os.path.dirname(__file__))
        template_folders = [
            os.path.join(repo_root, 'app/templates')
        ]
        jinja_loader = jinja2.FileSystemLoader(template_folders)
        app.jinja_loader = jinja_loader


class Test(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    DM_LOG_LEVEL = 'CRITICAL'
    WTF_CSRF_ENABLED = False

    DM_DATA_API_URL = "http://wrong.completely.invalid:5000"
    DM_DATA_API_AUTH_TOKEN = "myToken"

    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"
    SHARED_EMAIL_KEY = "KEY"
    SECRET_KEY = "KEY2"


class Development(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    SESSION_COOKIE_SECURE = False

    DM_DATA_API_URL = "http://localhost:5000"
    DM_DATA_API_AUTH_TOKEN = "myToken"

    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"
    SECRET_KEY = "verySecretKey"
    SHARED_EMAIL_KEY = "very_secret"


class Live(Config):
    """Base config for deployed environments"""
    DEBUG = False
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'
    DM_HTTP_PROTO = 'https'


class Preview(Live):
    pass


class Staging(Live):
    NOTIFY_TEMPLATES = {
        'reset_password': '4ae02cdd-65fd-417f-8c24-61260229f9af',
    }
    WTF_CSRF_ENABLED = False

    # Check we didn't forget any live template IDs
    assert NOTIFY_TEMPLATES.keys() == Config.NOTIFY_TEMPLATES.keys()


class Production(Live):
    NOTIFY_TEMPLATES = Staging.NOTIFY_TEMPLATES


configs = {
    'development': Development,
    'test': Test,
    'preview': Preview,
    'staging': Staging,
    'production': Production,
}
