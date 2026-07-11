"""
Django settings for config project.
"""

from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[]) + [
    "localhost", "127.0.0.1", ".vercel.app",
]

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[]) + [
    "https://*.vercel.app",
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'cursos',
    'matriculas',
    'pagamentos',
    'notificacoes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.ForcarTrocaSenhaMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cursos.context_processors.configuracao_site',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Local: SQLite (default). Futuro (Supabase): defina DATABASE_URL no .env
# com a connection string do Postgres, sem mudar nenhum código.

DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# Static / media files

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'cursos:minha_area'
LOGOUT_REDIRECT_URL = 'cursos:home'

# Gateway de pagamento: 'mock' por enquanto. Trocar por 'mercadopago'/'stripe'
# quando integrar de verdade — a factory em pagamentos/services.py lê essa flag.
PAYMENT_GATEWAY = env('PAYMENT_GATEWAY', default='mock')

# Notificações (email/whatsapp): 'mock' por enquanto, só loga em NotificacaoLog.
NOTIFICATION_BACKEND = env('NOTIFICATION_BACKEND', default='mock')

# Email de destino do admin pra receber notificação de nova matrícula (mock).
ADMIN_NOTIFICATION_EMAIL = env('ADMIN_NOTIFICATION_EMAIL', default='admin@saulocurso.local')
