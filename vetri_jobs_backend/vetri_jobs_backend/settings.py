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

    "cloudinary_storage",

    "cloudinary",



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


if os.getenv("DATABASE_URL"):

    # Production: Neon Postgres, configured via a single connection
    # string. Neon gives you this in one piece from your project
    # dashboard - it already includes sslmode=require, which Neon
    # requires.
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(
            default=os.getenv("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=True,
        )
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
# =====================================================
# SENDGRID EMAIL CONFIGURATION
# =====================================================

SENDGRID_API_KEY = os.getenv(
    "SENDGRID_API_KEY",
    ""
)

SENDGRID_SENDER_EMAIL = os.getenv(
    "SENDGRID_SENDER_EMAIL",
    ""
)

SENDGRID_SENDER_NAME = os.getenv(
    "SENDGRID_SENDER_NAME",
    "Vetri Jobs"
)


if SENDGRID_API_KEY:

    EMAIL_BACKEND = "jobsystem.email_backends.SendGridBackend"

else:

    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"



DEFAULT_FROM_EMAIL = SENDGRID_SENDER_EMAIL











EMAIL_HOST = os.getenv(

    "EMAIL_HOST",

    "smtp.gmail.com"

)



EMAIL_PORT = 587



EMAIL_USE_TLS = True


# Without this, a slow or unreachable SMTP server (e.g. outbound
# port 587 blocked/throttled by the host, or a DNS hiccup) makes
# Django's smtplib connection hang indefinitely. That's not just
# slow - it eventually triggers gunicorn's worker timeout, which
# SIGKILLs the entire worker process mid-request, taking down
# whatever request happened to be sending an email (e.g.
# registration) with a 500, even though the code around send_mail()
# already has a try/except for it. A timeout turns that hang into
# an actual raised exception the try/except can catch, so
# registration/notifications succeed even if the email itself fails.
# Only actually applies when EMAIL_BACKEND is the SMTP one above -
# harmless no-op when using BrevoAPIBackend, which sets its own
# 10s HTTPS request timeout instead.
EMAIL_TIMEOUT = 10



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


CACHES = {


"default":{


"BACKEND":

"django.core.cache.backends.redis.RedisCache",



"LOCATION":

"redis://127.0.0.1:6379/1"

}


}

# =====================================================
# CELERY
# =====================================================


CELERY_BROKER_URL = (

    "redis://127.0.0.1:6379/0"

)



CELERY_RESULT_BACKEND = (

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


    # Render (and most PaaS hosts) terminate HTTPS at a proxy and
    # forward the request to your app as plain HTTP. Without this,
    # Django thinks every request is insecure, which breaks
    # SECURE_SSL_REDIRECT (infinite redirect loop) and secure cookies.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


    # Required by Django 4+ for any HTTPS site with forms (e.g. Django
    # Admin login) - without your real domain listed here, admin login
    # fails with "CSRF verification failed. Origin checking failed."
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}"
        for host in ALLOWED_HOSTS
        if host not in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
    ]

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


STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# ==============================
# STATIC FILES
# ==============================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND":
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if (os.getenv("CLOUDINARY_URL") or os.getenv("CLOUDINARY_CLOUD_NAME"))
            else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# django-cloudinary-storage's own `collectstatic` override still checks
# this legacy pre-Django-4.2 setting directly and crashes with an
# AttributeError if it's missing. STORAGES above is what Django itself
# actually uses; this is just kept around so that package doesn't break.
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]


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


# Cloudinary - used for uploaded resumes, logos, and branding images
# in production (see STORAGES above). Leave these unset locally and
# uploads just go to the MEDIA_ROOT folder above instead.
def _clean_env(name):
    """Strip whitespace/newlines - a stray trailing newline from
    pasting into a multi-line env var field is a common, hard-to-spot
    cause of 'works locally, fails in production' credential bugs."""
    value = os.getenv(name, "")
    return value.strip() if value else value


_cloudinary_url = _clean_env("CLOUDINARY_URL")

if _cloudinary_url:

    # Preferred: Cloudinary's own single combined string, copied
    # straight from their dashboard's "API Environment variable"
    # button - one paste, so there's no way to mismatch cloud name
    # against the wrong key/secret. Format:
    # cloudinary://<api_key>:<api_secret>@<cloud_name>
    from urllib.parse import urlparse

    _parsed = urlparse(_cloudinary_url)

    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": _parsed.hostname,
        "API_KEY": _parsed.username,
        "API_SECRET": _parsed.password,
    }

else:

    # Fallback: three separate env vars
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": _clean_env("CLOUDINARY_CLOUD_NAME"),
        "API_KEY": _clean_env("CLOUDINARY_API_KEY"),
        "API_SECRET": _clean_env("CLOUDINARY_API_SECRET"),
    }




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
