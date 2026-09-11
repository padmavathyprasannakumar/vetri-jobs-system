"""
URL configuration for vetri_jobs_backend project.
"""

from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

from django.http import JsonResponse


# =====================================================
# BACKEND ROOT / API STATUS
# =====================================================

def api_root(request):

    return JsonResponse({

        "name": "Vetri Jobs Portal",

        "message": "Vetri Jobs Backend API is running",

        "status": "success",

        "api": "/api/",

        "admin": "/admin/",

    })


# =====================================================
# URL PATTERNS
# =====================================================

urlpatterns = [

    # -------------------------------------------------
    # Backend status
    # -------------------------------------------------

    path(
        "",
        api_root,
        name="api-root",
    ),


    # -------------------------------------------------
    # Django Admin
    # -------------------------------------------------

    path(
        "admin/",
        admin.site.urls,
    ),


    # -------------------------------------------------
    # REST API
    # -------------------------------------------------

    path(
        "api/",
        include("jobsystem.urls"),
    ),

]


# =====================================================
# MEDIA FILES
# Serving these unconditionally (not just when DEBUG=True) since
# this app currently has no separate static file server for media
# in production. When CLOUDINARY_* env vars are set, uploads go
# straight to Cloudinary and never hit this route at all - this is
# purely a fallback for any file that ended up on local disk (e.g.
# uploaded before Cloudinary was configured, or in an environment
# without Cloudinary credentials set).
# =====================================================

urlpatterns += static(

    settings.MEDIA_URL,

    document_root=settings.MEDIA_ROOT,

)
