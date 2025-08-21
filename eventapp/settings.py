from pathlib import Path
import firebase_admin
import environ
import os
import json
from firebase_admin import credentials
from celery.schedules import crontab
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Đọc các biến môi trường từ file .env
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='fallback-key')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = ["*", "eventapp-production-bcaa.up.railway.app", "localhost", "127.0.0.1"]

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'cloudinary',
    'cloudinary_storage',
    'events',
    'oauth2_provider',
    'drf_yasg',
    'social_django',
    "django_filters",
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True  # tam thoi cho nhanh khi connect expo
AUTH_USER_MODEL = 'events.User'

ROOT_URLCONF = 'eventapp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'eventapp.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'eventapp_db',           # Tên database bạn đã tạo
#         'USER': 'postgres',              # Tên người dùng PostgreSQL
#         'PASSWORD': '250304',            # Mật khẩu PostgreSQL
#         'HOST': '127.0.0.1',             # Hoặc địa chỉ IP của máy chủ database
#         'PORT': '5432',                  # Cổng mặc định của PostgreSQL
#     }
# }

DATABASES = {
    'default': dj_database_url.config(default=env('DATABASE_URL'))
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# cau hinh oauth2
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,  # số item mỗi trang, 10 sự kiện
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'OAuth2': {
            'type': 'oauth2',
            'flow': 'password',
            'tokenUrl': '/o/token/',
            'scopes': {
                'read': 'Read access',
                'write': 'Write access',
            }
        }
    }
}

# oauth2
# client_id = XumV2l3oVu7Y5dQLRiXF1f3q8vcA6tyKKXVTnsp1
# client_secret = iFG4l6Ng6tlsJLVvDhglbbuAzR5Z1kFBJMHHhgITMWRqdcSJdiG3pxQFnXPSFpDIMdFNKMoXwnGE1E04MlTfVIkRnwFUWQWLvHyZpItP1SNcAdcHbXNFIHJdmj1K3eW8

CLOUDINARY = {
    'cloud_name': 'dachbxwws',
    'api_key': '527949382554684',
    'api_secret': '1IKkyJfTMb_KR8LU0BIz1S9W_eQ'
}


AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

# cau hinh gg oauth
# try:
#     FIREBASE_CRED = credentials.Certificate('firebase_key.json')
#     firebase_admin.initialize_app(FIREBASE_CRED)
# except Exception as e:
#     print("Firebase init failed:", e)
try:
    firebase_json = env('FIREBASE_KEY')
    firebase_dict = json.loads(firebase_json)
    FIREBASE_CRED = credentials.Certificate(firebase_dict)
    firebase_admin.initialize_app(FIREBASE_CRED)
except Exception as e:
    print("Firebase init failed:", e)


OAUTH2_PROVIDER = {
    "OAUTH2_VALIDATOR_CLASS": "oauth2_provider.oauth2_validators.OAuth2Validator",
}

# MoMo settings
MOMO_PARTNER_CODE = env('MOMO_PARTNER_CODE')
MOMO_ACCESS_KEY = env('MOMO_ACCESS_KEY')
MOMO_SECRET_KEY = env('MOMO_SECRET_KEY')
MOMO_ENDPOINT = env('MOMO_ENDPOINT')
MOMO_REDIRECT_URL = env('MOMO_REDIRECT_URL')
MOMO_IPN_URL = env('MOMO_IPN_URL')

# Cau hinh Celery su dung Redis lam broker
CELERY_BROKER_URL = 'redis://localhost:6379/0'   # Ket noi den Redis local
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'


# Cau hinh timezone cho Celery
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# cau hinh gui mail khi thong bao nhac nho
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-relay.brevo.com'  # ten may chu SMTP cua Brevo
EMAIL_PORT = 587                     # cong TLS
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')         # thuong la email dang ky Brevo
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD') # SMTP Key tao trong Brevo
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')             # from address mac dinh


# tao periodic task (celery beat)
CELERY_BEAT_SCHEDULE = {
    'send-event-reminders-every-hour': {
        'task': 'events.tasks.send_event_reminders',
        'schedule': 3600,  # chay moi gio
    },
}

CSRF_TRUSTED_ORIGINS = [
    "https://eventapp-production-bcaa.up.railway.app",
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
