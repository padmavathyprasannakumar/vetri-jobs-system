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
# MEDIA FILES - DEVELOPMENT
# =====================================================

if settings.DEBUG:

    urlpatterns += static(

        settings.MEDIA_URL,

        document_root=settings.MEDIA_ROOT,

    )