from django.contrib import admin


from .models import (


    User,


    StudentProfile,

    CompanyProfile,

    PlacementAdminProfile,



    Education,

    Skill,

    Resume,



    Job,

    Application,

    CandidateReview,

    Interview,



    PlacementDrive,



    Notification,



    ChatbotSetting,

    ChatConversation,

    ChatMessage,



    WhatsAppSetting,

    WhatsAppMessage,



    Permission,

    CustomRole,

    RolePermission,



    PlatformAnalytics,


    SystemSetting,


    CMSContent,


    AuditLog,


)

from django.contrib import admin

from .models import Job





# =====================================================
# USER MANAGEMENT
# =====================================================


@admin.register(User)
class UserAdmin(admin.ModelAdmin):


    list_display = (

        "id",

        "username",

        "email",

        "role",

        "is_active",

        "is_staff",

    )


    list_filter = (

        "role",

        "is_active",

        "is_staff",

    )


    search_fields = (

        "username",

        "email",

    )


    # -------------------------------------------------
    # Without this, the admin's "Add User" form saves the
    # password field as plain text (Django's default
    # ModelAdmin has no idea `password` needs hashing) -
    # so any account created here couldn't actually log in.
    # This makes new/changed passwords go through
    # set_password() properly, same as the real
    # django.contrib.auth UserAdmin does.
    # -------------------------------------------------

    def save_model(self, request, obj, form, change):

        if "password" in form.changed_data:

            obj.set_password(obj.password)

        super().save_model(request, obj, form, change)







# =====================================================
# STUDENT
# =====================================================


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):


    list_display = (

        "user",

        "full_name",

        "verified",

        "created_at",

    )


    list_filter = (

        "verified",

    )


    search_fields = (

        "full_name",

        "user__email",

    )


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):

    list_display = (

        "student",

        "institution",

    )






@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):


    list_display = (

        "student",

        "name",

    )


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):

    list_display = (

        "student",

        "file",

    )








# =====================================================
# COMPANY
# =====================================================


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):


    list_display = (

        "user",

        "company_name",

        "approval_status",

        "verified",

        "created_at",

    )


    list_filter = (

        "approval_status",

        "verified",

    )


    search_fields = (

        "company_name",

        "user__email",

    )


    readonly_fields = (

        "registration_document_preview",

        "gst_document_preview",

        "photos_preview",

        "created_at",

        "updated_at",

    )


    fieldsets = (
        ("Account", {
            "fields": ("user", "company_name", "industry", "address", "phone", "contact_email"),
        }),
        ("Approval", {
            "fields": ("approval_status", "verified", "rejection_reason"),
        }),
        ("Submitted Documents", {
            "fields": (
                "registration_document", "registration_document_preview",
                "gst_document", "gst_document_preview",
                "photos_preview",
            ),
        }),
        ("Online Presence", {
            "fields": ("website", "linkedin", "twitter", "facebook", "instagram"),
        }),
        ("Meta", {
            "fields": ("created_at", "updated_at"),
        }),
    )


    actions = ["approve_companies", "reject_companies"]


    def registration_document_preview(self, obj):

        if obj.registration_document:

            return format_html(
                '<a href="{}" target="_blank">View registration document</a>',
                obj.registration_document.url,
            )

        return "Not uploaded"

    registration_document_preview.short_description = "Preview"


    def gst_document_preview(self, obj):

        if obj.gst_document:

            return format_html(
                '<a href="{}" target="_blank">View GST document</a>',
                obj.gst_document.url,
            )

        return "Not uploaded"

    gst_document_preview.short_description = "Preview"


    def photos_preview(self, obj):

        photos = obj.registration_photos.all() if obj.pk else []

        if not photos:

            return "No photos uploaded"

        return mark_safe(
            "".join(
                f'<a href="{p.photo.url}" target="_blank">'
                f'<img src="{p.photo.url}" style="height:80px;border-radius:8px;margin:4px;" />'
                f'</a>'
                for p in photos
            )
        )

    photos_preview.short_description = "Company Photos"


    def approve_companies(self, request, queryset):

        updated = queryset.update(approval_status="approved", verified=True)

        self.message_user(request, f"{updated} company(ies) approved.")

    approve_companies.short_description = "Approve selected companies"


    def reject_companies(self, request, queryset):

        updated = queryset.update(approval_status="rejected", verified=False)

        self.message_user(request, f"{updated} company(ies) rejected.")

    reject_companies.short_description = "Reject selected companies"









# =====================================================
# PLACEMENT ADMIN
# =====================================================


@admin.register(PlacementAdminProfile)
class PlacementAdminProfileAdmin(admin.ModelAdmin):


    list_display = (

        "user",

        "department",

        "designation",

    )








# =====================================================
# JOB ADMIN
# =====================================================


from django.contrib import admin

from .models import Job



@admin.register(Job)
class JobAdmin(admin.ModelAdmin):


    list_display = (

        "__str__",

        "status",

        "direct_apply_link",

    )


    # direct_apply_link is editable right on the list page too,
    # so a placement administrator can paste an external
    # application URL for a job without opening the full form.
    list_editable = (

        "direct_apply_link",

    )


    fields = (

        "company",

        "title",

        "description",

        "requirements",

        "skills_required",

        "qualification_required",

        "experience_required",

        "eligibility_criteria",

        "location",

        "salary",

        "job_type",

        "work_mode",

        "vacancies",

        "application_deadline",

        "interview_process",

        "direct_apply_link",

        "status",

        "is_active",

    )


    search_fields = (

        "title",

        "company__company_name",

    )

# =====================================================
# APPLICATIONS
# =====================================================


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):

    list_display = (

        "student",

        "job",

        "status",

        "applied_date",

    )


    list_filter = (

        "status",

    )








# =====================================================
# CANDIDATE REVIEW
# =====================================================


@admin.register(CandidateReview)
class CandidateReviewAdmin(admin.ModelAdmin):


    list_display = (

        "application",

        "shortlisted",

    )


# =====================================================
# INTERVIEW
# =====================================================


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):


    list_display = (

        "application",

        "interview_date",

        "status",

    )








# =====================================================
# PLACEMENT DRIVE
# =====================================================


@admin.register(PlacementDrive)
class PlacementDriveAdmin(admin.ModelAdmin):


    list_display = (

        "title",

        "created_at",

    )








# =====================================================
# NOTIFICATIONS
# =====================================================


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):


    list_display = (

        "user",

        "title",

        "is_read",

        "created_at",

    )


    list_filter = (

        "is_read",

    )








# =====================================================
# CHATBOT
# =====================================================


@admin.register(ChatbotSetting)
class ChatbotSettingAdmin(admin.ModelAdmin):


    list_display = (

        "name",

        "enabled",

    )








@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):

    list_display = (

        "user",

        "session_id",

    )




@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):


    list_display = (

        "conversation",

        "sender",

        "created_at",

    )








# =====================================================
# WHATSAPP
# =====================================================

@admin.register(WhatsAppSetting)
class WhatsAppSettingAdmin(admin.ModelAdmin):

    list_display = (

        "enabled",

    )







@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):


    list_display = (

        "phone_number",

        "status",

        "created_at",

    )








# =====================================================
# ROLE & PERMISSIONS
# =====================================================


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):


    list_display = (

        "name",

        "code",

    )








@admin.register(CustomRole)
class CustomRoleAdmin(admin.ModelAdmin):


    list_display = (

        "name",

    )








@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):


    list_display = (

        "role",

        "permission",

    )








# =====================================================
# ANALYTICS
# =====================================================

@admin.register(PlatformAnalytics)
class PlatformAnalyticsAdmin(admin.ModelAdmin):

    list_display = (

        "total_students",

        "total_companies",

        "total_jobs",

    )








# =====================================================
# SYSTEM SETTINGS
# =====================================================


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):


    list_display = (

        "key",

        "value",

    )








# =====================================================
# CMS
# =====================================================


@admin.register(CMSContent)
class CMSContentAdmin(admin.ModelAdmin):


    list_display = (

        "title",

        "is_active",

    )


    list_filter = (

        "is_active",

    )


    search_fields = (

        "title",

        "content",

    )


    search_fields = (

        "title",

        "content",

    )








# =====================================================
# AUDIT LOG
# =====================================================


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):


    list_display = (

        "user",

        "action",

        "created_at",

    )


    search_fields = (

        "action",

        "user__email",

    )

# =====================================================
# CHATBOT KNOWLEDGE BASE
# =====================================================

from .models import KnowledgeBaseEntry


@admin.register(KnowledgeBaseEntry)
class KnowledgeBaseEntryAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "category",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_active",
    )

    list_editable = (
        "is_active",
    )

    search_fields = (
        "title",
        "content",
    )


# =====================================================
# ADMIN CONTROLS (Requirement 28)
# =====================================================

from .models import (
    Department,
    Course,
    JobCategory,
    NotificationTemplate,
    WhatsAppTemplate,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):

    list_display = ("name", "code", "is_active")

    list_editable = ("code", "is_active")

    search_fields = ("name", "code")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):

    list_display = ("name", "department", "duration_years", "is_active")

    list_filter = ("department", "is_active")

    list_editable = ("is_active",)

    search_fields = ("name",)


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):

    list_display = ("name", "is_active")

    list_editable = ("is_active",)

    search_fields = ("name",)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):

    list_display = ("name", "event", "is_active", "updated_at")

    list_filter = ("event", "is_active")

    list_editable = ("is_active",)

    search_fields = ("name", "subject", "body")


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):

    list_display = ("name", "event", "is_active", "updated_at")

    list_filter = ("event", "is_active")

    list_editable = ("is_active",)

    search_fields = ("name", "message")


# =====================================================
# PLACEMENT QUERIES (raised via chatbot or forms)
# =====================================================

from .models import PlacementQuery


@admin.register(PlacementQuery)
class PlacementQueryAdmin(admin.ModelAdmin):

    list_display = ("student", "category", "status", "source", "created_at")

    list_filter = ("category", "status", "source")

    list_editable = ("status",)

    search_fields = ("student__full_name", "message")


# =====================================================
# SITE BRANDING (logo shown across the whole frontend)
# =====================================================

from django.utils.html import format_html

from django.utils.safestring import mark_safe

from .models import SiteBranding


@admin.register(SiteBranding)
class SiteBrandingAdmin(admin.ModelAdmin):

    list_display = ("site_name", "tagline", "logo_preview", "updated_at")

    readonly_fields = (
        "logo_preview_large",
        "register_hero_preview",
        "company_register_hero_preview",
        "dashboard_assistant_preview",
        "chatbot_avatar_preview",
        "profile_hero_preview",
        "homepage_hero_preview",
        "updated_at",
    )

    fieldsets = (
        ("General", {
            "fields": ("site_name", "tagline", "logo", "logo_preview_large", "favicon"),
        }),
        ("Homepage (public landing page)", {
            "fields": (
                "homepage_badge_text",
                "homepage_headline",
                "homepage_headline_highlight",
                "homepage_subtext",
                "homepage_hero_image",
                "homepage_hero_preview",
            ),
        }),
        ("Student Login page (left panel)", {
            "fields": ("login_headline", "login_subheadline"),
        }),
        ("Student Register page (left panel)", {
            "fields": ("register_hero_image", "register_hero_preview", "register_headline", "register_subheadline"),
        }),
        ("Company Login page (left panel)", {
            "fields": ("company_login_headline", "company_login_subheadline"),
        }),
        ("Company Register page (left panel)", {
            "fields": ("company_register_hero_image", "company_register_hero_preview", "company_register_headline", "company_register_subheadline"),
        }),
        ("Placement Admin Login page (left panel)", {
            "fields": ("placement_login_headline", "placement_login_subheadline"),
        }),
        ("Student Dashboard - AI Career Assistant card", {
            "fields": ("dashboard_assistant_image", "dashboard_assistant_preview"),
        }),
        ("Floating AI Chatbot avatar (site-wide)", {
            "fields": ("chatbot_avatar_image", "chatbot_avatar_preview"),
        }),
        ("Student Profile page (left panel)", {
            "fields": ("profile_hero_image", "profile_hero_preview"),
        }),
        ("Meta", {
            "fields": ("updated_at",),
        }),
    )

    def logo_preview(self, obj):

        if obj.logo:

            return format_html(
                '<img src="{}" style="height:30px;border-radius:6px;" />',
                obj.logo.url,
            )

        return "(no logo uploaded)"

    logo_preview.short_description = "Logo"

    def logo_preview_large(self, obj):

        if obj.logo:

            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:10px;" />',
                obj.logo.url,
            )

        return "Upload a logo and save - it will appear here, and "\
               "on every page of the site (navbar/sidebar) immediately."

    logo_preview_large.short_description = "Current logo"

    def register_hero_preview(self, obj):

        if obj.register_hero_image:

            return format_html(
                '<img src="{}" style="max-height:200px;border-radius:10px;" />',
                obj.register_hero_image.url,
            )

        return "No image uploaded - the Student Register page will show a " \
               "built-in illustration instead."

    register_hero_preview.short_description = "Preview"

    def company_register_hero_preview(self, obj):

        if obj.company_register_hero_image:

            return format_html(
                '<img src="{}" style="max-height:200px;border-radius:10px;" />',
                obj.company_register_hero_image.url,
            )

        return "No image uploaded - the Company Register page will show a " \
               "built-in illustration instead."

    company_register_hero_preview.short_description = "Preview"

    def dashboard_assistant_preview(self, obj):

        if obj.dashboard_assistant_image:

            return format_html(
                '<img src="{}" style="max-height:200px;border-radius:10px;" />',
                obj.dashboard_assistant_image.url,
            )

        return "No image uploaded - the AI Career Assistant card will " \
               "show a built-in illustration instead."

    dashboard_assistant_preview.short_description = "Preview"

    def chatbot_avatar_preview(self, obj):

        if obj.chatbot_avatar_image:

            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:50%;" />',
                obj.chatbot_avatar_image.url,
            )

        return "No image uploaded - the floating chatbot will show a " \
               "robot icon instead."

    chatbot_avatar_preview.short_description = "Preview"

    def profile_hero_preview(self, obj):

        if obj.profile_hero_image:

            return format_html(
                '<img src="{}" style="max-height:200px;border-radius:10px;" />',
                obj.profile_hero_image.url,
            )

        return "No image uploaded - the Profile page will show a " \
               "built-in illustration instead."

    profile_hero_preview.short_description = "Preview"

    def homepage_hero_preview(self, obj):

        if obj.homepage_hero_image:

            return format_html(
                '<img src="{}" style="max-height:220px;border-radius:10px;" />',
                obj.homepage_hero_image.url,
            )

        return "No image uploaded - the homepage will show a " \
               "built-in illustration instead."

    homepage_hero_preview.short_description = "Preview"

    def has_add_permission(self, request):

        # Singleton - only one branding record should ever exist.
        return not SiteBranding.objects.exists()

    def has_delete_permission(self, request, obj=None):

        return False


# =====================================================
# DJANGO ADMIN'S OWN BRANDING (top-left header text)
# =====================================================

admin.site.site_header = "Vetri Jobs Administration"

admin.site.site_title = "Vetri Jobs Admin"

admin.site.index_title = "Placement Ecosystem Control Panel"


# =====================================================
# NOTIFICATION ENGINE - per-event channel toggles
# =====================================================

from .models import NotificationChannelSetting


@admin.register(NotificationChannelSetting)
class NotificationChannelSettingAdmin(admin.ModelAdmin):

    list_display = (
        "event_key",
        "in_app_enabled",
        "email_enabled",
        "whatsapp_enabled",
    )

    list_editable = (
        "in_app_enabled",
        "email_enabled",
        "whatsapp_enabled",
    )

    def has_add_permission(self, request):

        # The 10 event rows are seeded by a migration - block
        # ad-hoc new rows so the set stays exactly matched to
        # what notification_engine.py actually dispatches for.
        return False

    def has_delete_permission(self, request, obj=None):

        return False
