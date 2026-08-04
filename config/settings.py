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

# Supabase (e poolers em geral, tipo PgBouncer/Supavisor) não seguram cursor
# nomeado entre comandos — quebra dumpdata/streams grandes com "cursor ...
# does not exist" quando a latência é maior (ex: VPS longe do pooler).
# Desabilita cursor no lado do Django pra qualquer Postgres; sem efeito
# prático pro tamanho de dado desse projeto.
if DATABASES['default'].get('ENGINE', '').endswith('postgresql'):
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True


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
STATIC_ROOT = BASE_DIR / '_staticfiles_build'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'cursos:minha_area'
LOGOUT_REDIRECT_URL = 'cursos:home'

# Gateway de pagamento (mock ou InfinitePay) e o InfiniteTag ficam na
# pagamentos.ConfiguracaoPagamento, editável em /painel/pagamento/ — não
# precisa de env var/redeploy pra trocar.

# Backend de notificação (mock ou SMTP real) e credenciais de email ficam na
# notificacoes.ConfiguracaoNotificacao, editável em /painel/notificacoes/ —
# não precisa de env var/redeploy pra trocar.

# Email de destino do admin pra receber notificação de nova matrícula.
ADMIN_NOTIFICATION_EMAIL = env('ADMIN_NOTIFICATION_EMAIL', default='admin@saulocurso.local')

# Endurecimento HTTPS — só em produção (DEBUG=False), depois que o certbot já
# está funcionando. nginx fala com o gunicorn em HTTP puro internamente, então
# o Django precisa do header abaixo pra saber que a requisição original era
# HTTPS (senão SECURE_SSL_REDIRECT vira loop infinito de redirecionamento).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Começa curto (1 semana) — dá pra aumentar depois que confirmar que o
    # HTTPS está estável. Valor alto de HSTS é difícil de reverter.
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
