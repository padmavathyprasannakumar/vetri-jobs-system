"""
Django settings for vetri_jobs_backend project.

Vetri Jobs Portal
Student Placement & Recruitment Platform
"""

import os

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

from datetime import timedelta


# =====================================================
# BASE DIRECTORY
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================================
# ENVIRONMENT HELPERS
# =====================================================

def env_bool(name, default=False):
    """
    Read boolean values from environment variables.
    """

    value = os.getenv(
        name,
        str(default)
    )

    return value.lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


def env_int(name, default):
    """
    Read integer values from environment variables.
    """

    return int(
        os.getenv(
            name,
            str(default)
        )
    )


# =====================================================
# SECURITY
# =====================================================

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-vetri-jobs-development-key"
)


DEBUG = env_bool(
    "DEBUG",
    True
)


ALLOWED_HOSTS = [

    "localhost",

    "127.0.0.1",

     "0.0.0.0",

     "[::1]",

] + [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
# =====================================================
# APPLICATIONS
# =====================================================


INSTALLED_APPS = [


    # Django Core

    "django.contrib.admin",

    "django.contrib.auth",

    "django.contrib.contenttypes",

    "django.contrib.sessions",

    "django.contrib.messages",

    "django.contrib.staticfiles",



    # Third Party

    "rest_framework",

    "rest_framework_simplejwt",

    "rest_framework_simplejwt.token_blacklist",

    "corsheaders",

    "django_filters",

    "drf_spectacular",



    # Project

    "jobsystem",

]








# =====================================================
# MIDDLEWARE
# =====================================================


MIDDLEWARE = [


    "corsheaders.middleware.CorsMiddleware",



    "django.middleware.security.SecurityMiddleware",



    "whitenoise.middleware.WhiteNoiseMiddleware",



    "django.contrib.sessions.middleware.SessionMiddleware",



    "django.middleware.common.CommonMiddleware",



    "django.middleware.csrf.CsrfViewMiddleware",



    "django.contrib.auth.middleware.AuthenticationMiddleware",



    "django.contrib.messages.middleware.MessageMiddleware",



    "django.middleware.clickjacking.XFrameOptionsMiddleware",


]








# =====================================================
# URL CONFIG
# =====================================================


ROOT_URLCONF = (

    "vetri_jobs_backend.urls"

)








# =====================================================
# TEMPLATES
# =====================================================


TEMPLATES = [

{

"BACKEND":

"django.template.backends.django.DjangoTemplates",


"DIRS":[],

"APP_DIRS":True,


"OPTIONS":{


"context_processors":[


"django.template.context_processors.request",


"django.contrib.auth.context_processors.auth",


"django.contrib.messages.context_processors.messages",


],


},


}

]








# =====================================================
# WSGI / ASGI
# =====================================================


WSGI_APPLICATION = (

"vetri_jobs_backend.wsgi.application"

)



ASGI_APPLICATION = (

"vetri_jobs_backend.asgi.application"

)

# =====================================================
# DATABASE
# =====================================================


if os.getenv("DB_HOST"):

    # Production: Postgres, configured via env vars
    # (set by your host, e.g. Render's managed Postgres add-on)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

else:

    # Local development: SQLite, no setup needed
    DATABASES = {


    "default":{


    "ENGINE":

    "django.db.backends.sqlite3",



    "NAME":

    BASE_DIR / "db.sqlite3"


    }


    }

# =====================================================
# CUSTOM USER MODEL
# =====================================================


AUTH_USER_MODEL = (

"jobsystem.User"

)

# =====================================================
# DJANGO REST FRAMEWORK
# =====================================================


REST_FRAMEWORK = {


    # =================================================
    # AUTHENTICATION
    # =================================================


    "DEFAULT_AUTHENTICATION_CLASSES":[


        "rest_framework_simplejwt.authentication.JWTAuthentication",


    ],






    # =================================================
    # DEFAULT PERMISSION
    # =================================================


    # All APIs protected by default
    #
    # Public APIs:
    #
    # Register
    # Login
    #
    # will override with AllowAny


    "DEFAULT_PERMISSION_CLASSES":[


        "rest_framework.permissions.IsAuthenticated",


    ],






    # =================================================
    # FILTERING
    # =================================================


    "DEFAULT_FILTER_BACKENDS":[


        "django_filters.rest_framework.DjangoFilterBackend"


    ],






    # =================================================
    # PAGINATION
    # =================================================


    "DEFAULT_PAGINATION_CLASS":


        "rest_framework.pagination.PageNumberPagination",



    "PAGE_SIZE":20,







    # =================================================
    # API DOCUMENTATION
    # =================================================


    "DEFAULT_SCHEMA_CLASS":


        "drf_spectacular.openapi.AutoSchema",






    # =================================================
    # RESPONSE FORMAT
    # =================================================


    "DEFAULT_RENDERER_CLASSES":[


        "rest_framework.renderers.JSONRenderer",



        "rest_framework.renderers.BrowsableAPIRenderer",


    ],


}


# =====================================================
# SIMPLE JWT
# Explicitly configured because without this, SimpleJWT
# falls back to its library default of a 5-minute access
# token lifetime - which is what was causing users to get
# logged out "randomly" mid-session (any 5+ minutes without
# a fresh API call, or a single refresh hiccup, forced a
# logout). Longer-lived tokens fix that without needing any
# frontend changes to the existing refresh-token flow.
# =====================================================

SIMPLE_JWT = {

    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),

    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": False,

    "BLACKLIST_AFTER_ROTATION": False,

    "UPDATE_LAST_LOGIN": True,

}




EMAIL_BACKEND = (

    "django.core.mail.backends.smtp.EmailBackend"

)



EMAIL_HOST = os.getenv(

    "EMAIL_HOST",

    "smtp.gmail.com"

)



EMAIL_PORT = 587



EMAIL_USE_TLS = True



EMAIL_HOST_USER = os.getenv(

    "EMAIL_HOST_USER",

    ""

)



EMAIL_HOST_PASSWORD = os.getenv(

    "EMAIL_HOST_PASSWORD",

    ""

)



DEFAULT_FROM_EMAIL = (

    EMAIL_HOST_USER

)

# =====================================================
# PASSWORD RESET
# =====================================================


PASSWORD_RESET_TIMEOUT = (

    60 * 60 * 24

)

# =====================================================
# AI CHATBOT SETTINGS
# =====================================================


AI_PROVIDER = os.getenv(

    "AI_PROVIDER",

    "openai"

)



OPENAI_API_KEY = os.getenv(

    "OPENAI_API_KEY",

    ""

)



GEMINI_API_KEY = os.getenv(

    "GEMINI_API_KEY",

    ""

)



GROQ_API_KEY = os.getenv(

    "GROQ_API_KEY",

    ""

)





AI_MODEL = os.getenv(

    "AI_MODEL",

    "gpt-4o-mini"

)

# =====================================================
# WHATSAPP CONFIGURATION
# =====================================================


WHATSAPP_ENABLED = True



WHATSAPP_PROVIDER = (

    "meta"

)



WHATSAPP_API_URL = os.getenv(

    "WHATSAPP_API_URL",

    ""

)



WHATSAPP_ACCESS_TOKEN = os.getenv(

    "WHATSAPP_ACCESS_TOKEN",

    ""

)



WHATSAPP_PHONE_NUMBER_ID = os.getenv(

    "WHATSAPP_PHONE_NUMBER_ID",

    ""

)

# =====================================================
# CACHE
# =====================================================
# CACHE

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/1"
)


CACHES = {

    "default": {

        "BACKEND":
        "django.core.cache.backends.redis.RedisCache",

        "LOCATION":
        REDIS_URL,

    }

}
# =====================================================
# CELERY
# =====================================================


CELERY_BROKER_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)


CELERY_RESULT_BACKEND = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)



CELERY_ACCEPT_CONTENT=[

    "json"

]



CELERY_TASK_SERIALIZER="json"



CELERY_RESULT_SERIALIZER="json"



CELERY_TIMEZONE="Asia/India"

# =====================================================
# LANGUAGE
# =====================================================


LANGUAGE_CODE="en-us"



TIME_ZONE="Asia/Kuala_Lumpur"



USE_I18N=True



USE_TZ=True

# =====================================================
# DATABASE DEFAULT
# =====================================================


DEFAULT_AUTO_FIELD = (

    "django.db.models.BigAutoField"

)

# =====================================================
# LOGGING
# =====================================================


LOGGING={


"version":1,


"disable_existing_loggers":False,


"handlers":{


"console":{


"class":

"logging.StreamHandler"

}


},



"loggers":{


"django":{


"handlers":[

"console"

],


"level":

"INFO"


},


"jobsystem":{


"handlers":[

"console"

],


"level":

"DEBUG"


}


}


}

# =====================================================
# SWAGGER / OPENAPI
# =====================================================


SPECTACULAR_SETTINGS = {


    "TITLE":

    "Vetri Jobs API",



    "DESCRIPTION":

    """
    Vetri Jobs Placement Portal API


    Modules:

    - Authentication
    - Students
    - Companies
    - Placement Admin
    - Super Admin
    - Chatbot
    - Notifications
    - WhatsApp

    """,



    "VERSION":

    "1.0.0",



    "SERVE_INCLUDE_SCHEMA":

    False,


}

# =====================================================
# SECURITY
# =====================================================


SECURE_BROWSER_XSS_FILTER=True


SECURE_CONTENT_TYPE_NOSNIFF=True


X_FRAME_OPTIONS="DENY"

# =====================================================
# HTTPS SECURITY
# =====================================================


if not DEBUG:


    SECURE_SSL_REDIRECT=True



    SESSION_COOKIE_SECURE=True



    CSRF_COOKIE_SECURE=True



    SECURE_HSTS_SECONDS=31536000



    SECURE_HSTS_INCLUDE_SUBDOMAINS=True



    SECURE_HSTS_PRELOAD=True

    # =====================================================
# PASSWORD VALIDATION
# =====================================================


AUTH_PASSWORD_VALIDATORS=[


{

"NAME":

"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"

},



{

"NAME":

"django.contrib.auth.password_validation.MinimumLengthValidator",

"OPTIONS":{

"min_length":8

}

},



{

"NAME":

"django.contrib.auth.password_validation.CommonPasswordValidator"

},



{

"NAME":

"django.contrib.auth.password_validation.NumericPasswordValidator"

},


]

# =====================================================
# FILE UPLOAD SETTINGS
# =====================================================


ALLOWED_RESUME_EXTENSIONS=[


    ".pdf",

    ".doc",

    ".docx"


]



MAX_RESUME_SIZE_MB=5

# =====================================================
# IMAGE UPLOAD
# =====================================================


ALLOWED_IMAGE_EXTENSIONS=[


    ".jpg",

    ".jpeg",

    ".png",

    ".webp"


]



MAX_IMAGE_SIZE_MB=3

# =====================================================
# FRONTEND URL
# =====================================================


FRONTEND_URL=os.getenv(

    "FRONTEND_URL",

    "http://localhost:5173"

)

# =====================================================
# EMAIL DEFAULTS
# =====================================================


EMAIL_SUBJECT_PREFIX="[Vetri Jobs] "

# =====================================================
# ADMIN
# =====================================================


ADMIN_URL="secure-admin/"




# ==============================
# STATIC FILES
# ==============================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


STATICFILES_DIRS = [

    BASE_DIR / "static",

]


# ==============================
# MEDIA FILES (uploaded resumes, company logos, etc.)
# Required so uploaded files actually get served/have working
# URLs - these were never defined even though urls.py referenced
# them, which is why uploaded logos/resumes showed a broken image.
# ==============================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"




# =====================================================
# CORS CONFIGURATION
# =====================================================

CORS_ALLOWED_ORIGINS = [

    "http://localhost:5173",

    "http://127.0.0.1:5173",

    "http://localhost:5175",

    "http://127.0.0.1:5175",

] + [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]


CORS_ALLOW_CREDENTIALS = True


GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)