from django.urls import path

# Lets the frontend swap an expired access token for a new one
# (POST /api/token/refresh/ with {"refresh": "<refresh token>"}).
# Without this route the frontend got a 404 when the login token
# expired, logged the user out, and the chatbot showed
# "Unable to connect with assistant".
from rest_framework_simplejwt.views import TokenRefreshView


from .views import (

    # =====================================================
    # AUTH
    # =====================================================

    RegisterView,
    CompanyRegisterView,
    CompanyRegistrationStatusView,
    LoginView,
    ForgotPasswordView,
    ResetPasswordConfirmView,
    CurrentUserView,
    LogoutView,
    UpdateProfileView,


    # =====================================================
    # STUDENT
    # =====================================================

    StudentProfileView,
    EducationListCreateView,
    SkillCreateView,
    ResumeUploadView,
    StudentJobListView,
    ApplyJobView,
    StudentApplicationsView,
    StudentInterviewView,
    StudentNotificationView,
    ResumeAPIView,

    StudentDashboardView,

    ResumeListView,
    ResumeDownloadView,
    ResumeDeleteView,
    ResumeAnalyzeView,

    # Student Resume page (upload/replace, versions, delete,
    # download, AI analyse) - added without removing anything above
    StudentResumeVersionsView,
    StudentResumeDetailView,
    StudentResumeDownloadView,
    StudentResumeAnalyseView,

    # Saved jobs (wishlist)
    SaveJobView,
    StudentSavedJobsView,
    StudentJobDetailView,
    LookupListsView,
    SiteBrandingView,
    EligibilityCheckView,


    # =====================================================
    # COMPANY
    # =====================================================

    CompanyProfileView,
    CompanyCreateJobView,
    CompanyJobListView,
    CompanyJobUpdateView,
    CompanyJobDeleteView,
    CompanyCandidateSearchView,
    CompanyCandidatesView,
    CandidateReviewCreateView,
    ShortlistCandidateView,
    CompanyApplicationStatusView,
    CompanyCandidateNotesView,
    CandidateProfileViewedView,
    CompanyInterviewCreateView,
    CompanyDashboardView,
    CompanyLogoUploadView,
    CompanyInterviewListView,
    CompanyInterviewStatusUpdateView,
    CompanyAnalyticsView,


    # =====================================================
    # PLACEMENT ADMIN
    # =====================================================

    PlacementDashboardView,
    PlacementDriveDetailView,
    PlacementCandidatePipelineView,
    PlacementStudentListView,
    VerifyStudentView,
    PlacementStudentUpdateView,
    PlacementStudentStatusUpdateView,
    PlacementStudentCreateView,
    PlacementJobListView,
    PlacementJobStatusUpdateView,
    PlacementCompanyHistoryView,
    PlacementCompanyListView,
    VerifyCompanyView,
    RejectCompanyView,
    CreatePlacementDriveView,
    PlacementDriveListView,
    PlacementApplicationListView,
    PlacementUpdateApplicationView,
    PlacementNotificationCreateView,
    SendNotificationView,
    PlacementReportView,
    ScheduleReportView,


    # =====================================================
    # SUPER ADMIN
    # =====================================================

    AdminDashboardView,
    AdminUserListView,
    AdminUserUpdateView,
    AdminDeleteUserView,

    PermissionCreateView,
    PermissionListView,

    RolePermissionCreateView,

    CustomRoleListCreateView,

    AdminStudentListView,

    AdminCompanyListView,

    AdminJobListView,

    AdminAnalyticsView,

    AdminAuditLogView,

    SystemSettingView,


    # =====================================================
    # CHATBOT
    # =====================================================

    ChatConversationCreateView,
    ChatMessageCreateView,
    ChatHistoryView,
    ChatbotSettingView,
    WhatsAppWebhookView,
    ChatbotMessageAPIView,
    ChatbotHistoryAPIView,
    ChatbotProactiveView,        # NEW - proactive alerts for the chat widget


    # =====================================================
    # WHATSAPP
    # =====================================================

    WhatsAppSettingView,
    WhatsAppMessageCreateView,


    # =====================================================
    # NOTIFICATION
    # =====================================================

    NotificationListView,
    NotificationReadView,
    NotificationDeleteView,
    NotificationMarkAllReadView,
    CreateNotificationView,


    # =====================================================
    # CMS
    # =====================================================

    CMSContentView,

    JobListAPIView,

)


urlpatterns = [


    # =====================================================
    # AUTHENTICATION
    # =====================================================


    path(
        "auth/register/",
        RegisterView.as_view(),
        name="register"
    ),


    path(
        "company/register/",
        CompanyRegisterView.as_view(),
        name="company-register"
    ),


    path(
        "company/application-status/",
        CompanyRegistrationStatusView.as_view(),
        name="company-application-status"
    ),


    path(
        "auth/login/",
        LoginView.as_view(),
        name="login"
    ),


    path(
        "auth/forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password"
    ),


    path(
        "auth/reset-password-confirm/",
        ResetPasswordConfirmView.as_view(),
        name="reset-password-confirm"
    ),


    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh"
    ),


    path(
        "auth/me/",
        CurrentUserView.as_view(),
        name="current-user"
    ),


    path(
        "auth/logout/",
        LogoutView.as_view(),
        name="logout"
    ),


    path(
        "profile/update/",
        UpdateProfileView.as_view(),
        name="profile-update"
    ),


    # =====================================================
    # STUDENT MODULE
    # =====================================================


    path(
        "student/profile/",
        StudentProfileView.as_view(),
        name="student-profile"
    ),


    path(
        "student/education/",
        EducationListCreateView.as_view(),
        name="student-education"
    ),


    path(
        "student/skills/",
        SkillCreateView.as_view(),
        name="student-skills"
    ),


    path(
        "student/resume/",
        ResumeUploadView.as_view(),
        name="student-resume"
    ),


    # ---------------------------------------------------------
    # Additional student-resume endpoints used by the
    # Resume Management page (upload/replace, versions,
    # delete, download, AI analyse). Added alongside the
    # existing "resume/*" endpoints above without touching them.
    # ---------------------------------------------------------

    path(
        "student/resume/versions/",
        StudentResumeVersionsView.as_view(),
        name="student-resume-versions"
    ),


    path(
        "student/resume/<int:id>/",
        StudentResumeDetailView.as_view(),
        name="student-resume-detail"
    ),


    path(
        "student/resume/<int:id>/download/",
        StudentResumeDownloadView.as_view(),
        name="student-resume-download"
    ),


    path(
        "student/resume/<int:id>/analyse/",
        StudentResumeAnalyseView.as_view(),
        name="student-resume-analyse"
    ),


    path(
        "student/jobs/",
        StudentJobListView.as_view(),
        name="student-jobs"
    ),


    path(
        "student/jobs/<int:job_id>/",
        StudentJobDetailView.as_view(),
        name="student-job-detail"
    ),


    path(
        "student/jobs/<int:job_id>/apply/",
        ApplyJobView.as_view(),
        name="apply-job"
    ),


    path(
        "student/jobs/<int:job_id>/save/",
        SaveJobView.as_view(),
        name="save-job"
    ),


    path(
        "student/saved-jobs/",
        StudentSavedJobsView.as_view(),
        name="student-saved-jobs"
    ),


    path(
        "student/jobs/<int:job_id>/eligibility/",
        EligibilityCheckView.as_view(),
        name="student-job-eligibility"
    ),


    path(
        "student/applications/",
        StudentApplicationsView.as_view(),
        name="student-applications"
    ),


    path(
        "student/interviews/",
        StudentInterviewView.as_view(),
        name="student-interviews"
    ),


    path(
        "student/notifications/",
        StudentNotificationView.as_view(),
        name="student-notifications"
    ),


    path(
        "student/dashboard/",
        StudentDashboardView.as_view(),
        name="student-dashboard"
    ),


    # =====================================================
    # RESUME MANAGEMENT + AI ANALYSIS
    # =====================================================


    path(
        "resume/upload/",
        ResumeUploadView.as_view(),
        name="resume-upload"
    ),


    path(
        "resume/list/",
        ResumeListView.as_view(),
        name="resume-list"
    ),


    path(
        "resume/download/<int:id>/",
        ResumeDownloadView.as_view(),
        name="resume-download"
    ),


    path(
        "resume/delete/<int:id>/",
        ResumeDeleteView.as_view(),
        name="resume-delete"
    ),


    path(
        "resume/analyze/<int:id>/",
        ResumeAnalyzeView.as_view(),
        name="resume-analyze"
    ),


    # =====================================================
    # COMPANY MODULE
    # =====================================================


    path(
        "company/dashboard/",
        CompanyDashboardView.as_view(),
        name="company-dashboard"
    ),


    path(
        "company/analytics/",
        CompanyAnalyticsView.as_view(),
        name="company-analytics"
    ),


    path(
        "company/profile/",
        CompanyProfileView.as_view(),
        name="company-profile"
    ),


    path(
        "company/profile/logo/",
        CompanyLogoUploadView.as_view(),
        name="company-profile-logo"
    ),


    path(
        "company/jobs/create/",
        CompanyCreateJobView.as_view(),
        name="company-create-job"
    ),


    path(
        "company/jobs/",
        CompanyJobListView.as_view(),
        name="company-jobs"
    ),


    path(
        "company/jobs/<int:job_id>/update/",
        CompanyJobUpdateView.as_view(),
        name="company-job-update"
    ),


    path(
        "company/jobs/<int:job_id>/delete/",
        CompanyJobDeleteView.as_view(),
        name="company-job-delete"
    ),


    path(
        "company/candidates/search/",
        CompanyCandidateSearchView.as_view(),
        name="company-candidate-search"
    ),


    path(
        "company/candidates/",
        CompanyCandidatesView.as_view(),
        name="company-candidates"
    ),


    path(
        "company/candidates/<int:application_id>/review/",
        CandidateReviewCreateView.as_view(),
        name="candidate-review"
    ),


    path(
        "company/review/<int:review_id>/shortlist/",
        ShortlistCandidateView.as_view(),
        name="candidate-shortlist"
    ),


    path(
        "company/application/<int:application_id>/status/",
        CompanyApplicationStatusView.as_view(),
        name="application-status"
    ),


    path(
        "company/candidates/<int:application_id>/status/",
        CompanyApplicationStatusView.as_view(),
        name="candidate-status-alias"
    ),


    path(
        "company/candidates/<int:application_id>/notes/",
        CompanyCandidateNotesView.as_view(),
        name="candidate-notes"
    ),


    path(
        "company/candidates/<int:application_id>/viewed/",
        CandidateProfileViewedView.as_view(),
        name="candidate-profile-viewed"
    ),


    path(
        "company/interviews/create/",
        CompanyInterviewCreateView.as_view(),
        name="create-interview"
    ),


    path(
        "company/interviews/",
        CompanyInterviewListView.as_view(),
        name="company-interviews-list"
    ),


    path(
        "company/interviews/<int:interview_id>/status/",
        CompanyInterviewStatusUpdateView.as_view(),
        name="company-interview-status"
    ),


    path(
        "jobs/",
        JobListAPIView.as_view()
    ),


    path(
        "lookups/",
        LookupListsView.as_view(),
        name="lookup-lists"
    ),


    path(
        "site-branding/",
        SiteBrandingView.as_view(),
        name="site-branding"
    ),


    # =====================================================
    # PLACEMENT ADMIN
    # =====================================================


    path(
        "placement/dashboard/",
        PlacementDashboardView.as_view(),
        name="placement-dashboard"
    ),


    path(
        "placement/students/",
        PlacementStudentListView.as_view(),
        name="placement-students"
    ),


    path(
        "placement/students/<int:student_id>/verify/",
        VerifyStudentView.as_view(),
        name="verify-student"
    ),


    path(
        "placement/students/<int:student_id>/",
        PlacementStudentUpdateView.as_view(),
        name="update-placement-student"
    ),


    path(
        "placement/students/create/",
        PlacementStudentCreateView.as_view(),
        name="create-placement-student"
    ),


    path(
        "placement/students/<int:student_id>/status/",
        PlacementStudentStatusUpdateView.as_view(),
        name="placement-student-status"
    ),


    path(
        "placement/companies/",
        PlacementCompanyListView.as_view(),
        name="placement-companies"
    ),


    path(
        "placement/jobs/",
        PlacementJobListView.as_view(),
        name="placement-jobs"
    ),


    path(
        "placement/jobs/<int:job_id>/status/",
        PlacementJobStatusUpdateView.as_view(),
        name="placement-job-status-update"
    ),


    path(
        "placement/companies/<int:company_id>/history/",
        PlacementCompanyHistoryView.as_view(),
        name="placement-company-history"
    ),


    path(
        "placement/companies/<int:company_id>/verify/",
        VerifyCompanyView.as_view(),
        name="verify-company"
    ),


    path(
        "placement/companies/<int:company_id>/reject/",
        RejectCompanyView.as_view(),
        name="reject-company"
    ),


    path(
        "placement/drives/create/",
        CreatePlacementDriveView.as_view(),
        name="create-placement-drive"
    ),


    path(
        "placement/drives/",
        PlacementDriveListView.as_view(),
        name="placement-drives"
    ),


    path(
        "placement/drives/<int:drive_id>/",
        PlacementDriveDetailView.as_view(),
        name="placement-drive-detail"
    ),


    path(
        "placement/drives/<int:drive_id>/status/",
        PlacementDriveDetailView.as_view(),
        name="placement-drive-status"
    ),


    path(
        "placement/applications/",
        PlacementApplicationListView.as_view(),
        name="placement-applications"
    ),


    path(
        "placement/candidates/pipeline/",
        PlacementCandidatePipelineView.as_view(),
        name="placement-candidate-pipeline"
    ),


    path(
        "placement/application/<int:application_id>/status/",
        PlacementUpdateApplicationView.as_view(),
        name="placement-update-status"
    ),


    path(
        "placement/notifications/create/",
        PlacementNotificationCreateView.as_view(),
        name="placement-notification"
    ),


    path(
        "notifications/send/",
        SendNotificationView.as_view(),
        name="send-notification"
    ),


    path(
        "placement/reports/",
        PlacementReportView.as_view(),
        name="placement-report"
    ),


    path(
        "placement/reports/schedule/",
        ScheduleReportView.as_view(),
        name="placement-report-schedule"
    ),


    # =====================================================
    # SUPER ADMIN
    # =====================================================


    path(
        "admin/dashboard/",
        AdminDashboardView.as_view(),
        name="admin-dashboard"
    ),


    path(
        "admin/users/",
        AdminUserListView.as_view(),
        name="admin-users"
    ),


    path(
        "admin/users/<int:user_id>/update/",
        AdminUserUpdateView.as_view(),
        name="admin-user-update"
    ),


    path(
        "admin/users/<int:user_id>/delete/",
        AdminDeleteUserView.as_view(),
        name="admin-user-delete"
    ),


    path(
        "admin/permissions/",
        PermissionListView.as_view(),
        name="permissions"
    ),


    path(
        "admin/permissions/create/",
        PermissionCreateView.as_view(),
        name="create-permission"
    ),


    path(
        "admin/role-permissions/",
        RolePermissionCreateView.as_view(),
        name="role-permission"
    ),


    path(
        "admin/roles/",
        CustomRoleListCreateView.as_view(),
        name="roles"
    ),


    path(
        "admin/students/",
        AdminStudentListView.as_view(),
        name="admin-students"
    ),


    path(
        "admin/companies/",
        AdminCompanyListView.as_view(),
        name="admin-companies"
    ),


    path(
        "admin/jobs/",
        AdminJobListView.as_view(),
        name="admin-jobs"
    ),


    path(
        "admin/analytics/",
        AdminAnalyticsView.as_view(),
        name="admin-analytics"
    ),


    path(
        "admin/audit-logs/",
        AdminAuditLogView.as_view(),
        name="audit-logs"
    ),


    path(
        "admin/settings/",
        SystemSettingView.as_view(),
        name="system-settings"
    ),


    # =====================================================
    # CHATBOT
    # =====================================================


    path(
        "whatsapp/webhook/",
        WhatsAppWebhookView.as_view(),
        name="whatsapp-webhook"
    ),


    path(
        "chatbot/",
        ChatbotMessageAPIView.as_view(),
        name="chatbot-message-unified"
    ),


    # NEW - the chat widget polls this every ~60s for proactive alerts
    # (interview soon, unread notifications, new jobs, etc.)
    path(
        "chatbot/proactive/",
        ChatbotProactiveView.as_view(),
        name="chatbot-proactive"
    ),


    path(
        "chatbot/history/",
        ChatbotHistoryAPIView.as_view(),
        name="chatbot-history-unified"
    ),


    path(
        "chatbot/conversation/",
        ChatConversationCreateView.as_view(),
        name="chat-create"
    ),


    path(
        "chatbot/message/",
        ChatMessageCreateView.as_view(),
        name="chat-message"
    ),


    path(
        "chatbot/history/<int:conversation_id>/",
        ChatHistoryView.as_view(),
        name="chat-history"
    ),


    path(
        "chatbot/settings/",
        ChatbotSettingView.as_view(),
        name="chat-settings"
    ),


    # =====================================================
    # WHATSAPP
    # =====================================================


    path(
        "whatsapp/settings/",
        WhatsAppSettingView.as_view(),
        name="whatsapp-settings"
    ),


    path(
        "whatsapp/send/",
        WhatsAppMessageCreateView.as_view(),
        name="whatsapp-send"
    ),


    # =====================================================
    # NOTIFICATIONS
    # =====================================================


    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notifications"
    ),


    path(
        "notifications/<int:notification_id>/read/",
        NotificationReadView.as_view(),
        name="notification-read"
    ),


    path(
        "notifications/<int:notification_id>/delete/",
        NotificationDeleteView.as_view(),
        name="notification-delete"
    ),


    path(
        "notifications/mark-all-read/",
        NotificationMarkAllReadView.as_view(),
        name="notification-mark-all-read"
    ),


    path(
        "notifications/create/",
        CreateNotificationView.as_view(),
        name="notification-create"
    ),


    # =====================================================
    # CMS
    # =====================================================


    path(
        "cms/",
        CMSContentView.as_view(),
        name="cms"
    ),


]
