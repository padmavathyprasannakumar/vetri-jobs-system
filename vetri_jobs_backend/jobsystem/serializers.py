from rest_framework import serializers

from .models import (

    User,

    Permission,

    RolePermission,

    StudentProfile,

    CompanyProfile,

    PlacementAdminProfile,

    Education,

    Skill,

    Resume,

    Experience,

    Job,

    Application,

    CandidateReview,

    Interview,

    PlacementDrive,

    Notification,

    SystemSetting,

    ChatConversation,

    ChatMessage,

    ChatbotSetting,

    WhatsAppSetting,

    WhatsAppMessage,

    AuditLog,

    PlatformAnalytics,

    CMSContent,

    AdminSetting,

    CustomRole,

    LoginHistory,

    SupportTicket,
    ResumeAnalysis,


)


from rest_framework import serializers
from .models import Job



# =====================================================
# USER SERIALIZER
# =====================================================


class UserSerializer(serializers.ModelSerializer):


    class Meta:


        model = User


        fields = [

            "id",

            "username",

            "email",

            "phone",

            "whatsapp_number",

            "role",

            "profile_image",

            "is_verified",

            "is_active",

            "created_at"

        ]



        read_only_fields = [

            "is_verified",

            "created_at"

        ]









# =====================================================
# REGISTER SERIALIZER
# Vetri Jobs
# Student + Company Registration
# =====================================================


class RegisterSerializer(serializers.ModelSerializer):


    password = serializers.CharField(

        write_only=True

    )


    confirm_password = serializers.CharField(

        write_only=True

    )



    # =====================================================
    # STUDENT FIELDS
    # =====================================================


    full_name = serializers.CharField(

        required=False,

        allow_blank=True

    )


    student_id = serializers.CharField(

        required=False,

        allow_blank=True

    )


    course = serializers.CharField(

        required=False,

        allow_blank=True

    )


    department = serializers.CharField(

        required=False,

        allow_blank=True

    )


    graduation_year = serializers.IntegerField(

        required=False,

        allow_null=True

    )




    # =====================================================
    # COMPANY FIELDS
    # =====================================================


    company_name = serializers.CharField(

        required=False,

        allow_blank=True

    )


    industry = serializers.CharField(

        required=False,

        allow_blank=True

    )






    class Meta:


        model = User


        fields = [


            # USER

            "username",

            "email",

            "phone",

            "password",

            "confirm_password",

            "role",



            # STUDENT

            "full_name",

            "student_id",

            "course",

            "department",

            "graduation_year",



            # COMPANY

            "company_name",

            "industry"


        ]







    # =====================================================
    # VALIDATION
    # =====================================================


    def validate(self,data):


        password = data.get(
            "password"
        )


        confirm_password = data.get(
            "confirm_password"
        )



        if password != confirm_password:


            raise serializers.ValidationError({


                "password":

                "Password does not match"


            })





        if User.objects.filter(

            username=data.get("username")

        ).exists():


            raise serializers.ValidationError({


                "username":

                "Username already exists"


            })







        if User.objects.filter(

            email=data.get("email")

        ).exists():


            raise serializers.ValidationError({


                "email":

                "Email already exists"


            })




        return data







    # =====================================================
    # CREATE USER + PROFILE
    # =====================================================


    def create(self,validated_data):


        # remove password confirmation

        validated_data.pop(

            "confirm_password",

            None

        )





        # =================================================
        # EXTRACT STUDENT DATA
        # =================================================


        full_name = validated_data.pop(

            "full_name",

            ""

        )


        student_id = validated_data.pop(

            "student_id",

            ""

        )


        course = validated_data.pop(

            "course",

            ""

        )


        department = validated_data.pop(

            "department",

            ""

        )


        graduation_year = validated_data.pop(

            "graduation_year",

            None

        )






        # =================================================
        # EXTRACT COMPANY DATA
        # =================================================


        company_name = validated_data.pop(

            "company_name",

            ""

        )


        industry = validated_data.pop(

            "industry",

            ""

        )






        # =================================================
        # CREATE USER
        # =================================================


        user = User.objects.create_user(


            username=

            validated_data.get(

                "username"

            ),



            email=

            validated_data.get(

                "email"

            ),



            phone=

            validated_data.get(

                "phone"

            ),



            password=

            validated_data.get(

                "password"

            ),



            role=

            validated_data.get(

                "role",

                "student"

            )


        )









        # =================================================
        # CREATE STUDENT PROFILE
        # =================================================


        if user.role == "student":



            StudentProfile.objects.create(


                user=user,


                full_name=full_name,


                student_id=student_id,


                course=course,


                department=department,


                graduation_year=graduation_year,


                profile_completion=20


            )









        # =================================================
        # CREATE COMPANY PROFILE
        # =================================================


        elif user.role == "company":



            CompanyProfile.objects.create(


                user=user,


                company_name=company_name,


                industry=industry


            )







        return user


# =====================================================
# LOGIN SERIALIZER
# =====================================================


from django.contrib.auth import authenticate
from rest_framework import serializers



class LoginSerializer(serializers.Serializer):


    email = serializers.EmailField()


    password = serializers.CharField(
        write_only=True
    )




    def validate(self,data):


        email = data.get(
            "email"
        )


        password = data.get(
            "password"
        )



        user = authenticate(

            username=email,

            password=password

        )



        if not user:


            raise serializers.ValidationError(

                "Invalid credentials"

            )



        if not user.is_active:


            raise serializers.ValidationError(

                "Account is disabled"

            )



        data["user"] = user


        return data




# =====================================================
# PERMISSION SERIALIZER
# =====================================================


class PermissionSerializer(serializers.ModelSerializer):


    class Meta:


        model = Permission


        fields="__all__"









# =====================================================
# ROLE PERMISSION SERIALIZER
# =====================================================


class RolePermissionSerializer(serializers.ModelSerializer):


    permission = PermissionSerializer(

        read_only=True

    )



    class Meta:


        model = RolePermission


        fields="__all__"








# =====================================================
# CUSTOM ROLE SERIALIZER
# =====================================================


class CustomRoleSerializer(serializers.ModelSerializer):


    permissions = PermissionSerializer(

        many=True,

        read_only=True

    )



    class Meta:


        model = CustomRole


        fields="__all__"

# =====================================================
# STUDENT PROFILE SERIALIZER
# =====================================================


class StudentProfileSerializer(serializers.ModelSerializer):


    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )


    phone = serializers.CharField(
        source="user.phone",
        required=False,
        allow_blank=True
    )



    class Meta:


        model = StudentProfile


        fields = [

            "id",

            "verified",

            "placement_status",

            # USER DATA

            "email",

            "phone",



            # PERSONAL

            "full_name",

            "student_id",

            "date_of_birth",

            "gender",

            "location",



            # ACADEMIC

            "institution",

            "course",

            "department",

            "graduation_year",

            "tenth_percentage",

            "twelfth_percentage",

            "ug_cgpa",

            "diploma_details",

            "pg_details",



            # PROFESSIONAL

            "skills",

            "certifications",

            "projects",

            "internships",

            "experience",

            "languages",

            "portfolio",

            "github",

            "linkedin",



            # RESUME

            "resume",



            # SYSTEM

            "profile_completion",

            "created_at",

            "updated_at"

        ]



        read_only_fields=[

            "id",

            "verified",

            "profile_completion",

            "created_at",

            "updated_at"

        ]



# =====================================================
# STUDENT DASHBOARD SERIALIZER
# =====================================================


class StudentDashboardSerializer(serializers.Serializer):


    profile_completion = serializers.IntegerField()


    total_jobs = serializers.IntegerField()


    applied_jobs = serializers.IntegerField()


    shortlisted = serializers.IntegerField()


    interviews = serializers.IntegerField()


    selected = serializers.IntegerField()


    recommended_jobs = serializers.ListField()


    notifications = serializers.ListField()

    # =====================================================
    # UPDATE PROFILE
    # =====================================================


    def update(self,instance,validated_data):


        user_data = validated_data.pop(

            "user",

            {}

        )


        # update student fields

        for attr,value in validated_data.items():


            setattr(

                instance,

                attr,

                value

            )


        instance.save()



        # update user phone

        if "phone" in user_data:


            instance.user.phone = (

                user_data["phone"]

            )


            instance.user.save()



        return instance





# =====================================================
# EDUCATION SERIALIZER
# =====================================================


class EducationSerializer(serializers.ModelSerializer):


    class Meta:


        model = Education


        fields = "__all__"




    def create(self,validated_data):


        return Education.objects.create(

            **validated_data

        )







# =====================================================
# SKILL SERIALIZER
# =====================================================


class SkillSerializer(serializers.ModelSerializer):


    class Meta:


        model = Skill


        fields = "__all__"







# =====================================================
# RESUME SERIALIZER
# =====================================================


from rest_framework import serializers
from .models import Resume, ResumeAnalysis


class ResumeSerializer(serializers.ModelSerializer):

    file_url = serializers.SerializerMethodField()

    # -----------------------------------------------------
    # Aliases kept alongside the original fields above so
    # existing consumers of "file_url"/"filename" keep working
    # while the student-portal frontend (which expects
    # "resume_url" / "file_name") also gets what it needs.
    # -----------------------------------------------------

    resume_url = serializers.SerializerMethodField()

    file_name = serializers.SerializerMethodField()


    file_size = serializers.SerializerMethodField()


    class Meta:

        model = Resume

        fields = [

            "id",

            "student",

            "file",

            "file_url",

            "resume_url",

            "filename",

            "file_name",

            "file_size",

            "uploaded_at",

            "updated_at",

            "is_active",


            # AI Analysis Result

            "resume_score",

            "skills",

            "experience",

            "education",

            "certifications",

            "projects",

            "missing_information",

            "job_categories",

            "extracted_text",

        ]


        read_only_fields = [

            "student",

            "uploaded_at",

            "updated_at",

            "resume_score",

            "skills",

            "experience",

            "education",

            "certifications",

            "projects",

            "missing_information",

            "job_categories",

            "extracted_text",

        ]


    def get_file_url(self, obj):

        request = self.context.get(
            "request"
        )

        if obj.file:

            if request:

                return request.build_absolute_uri(
                    obj.file.url
                )

            return obj.file.url

        return None


    def get_resume_url(self, obj):

        # Same value as file_url, exposed under the name the
        # student-portal Resume page reads (resume.resume_url).

        return self.get_file_url(obj)


    def get_file_name(self, obj):

        # Same value as filename, exposed under the name the
        # student-portal Resume page reads (resume.file_name).

        return obj.filename


    def get_file_size(self, obj):

        # Human-readable size (e.g. "245 KB") for the Resume
        # Management page's file listings.
        #
        # obj.file.size can come back as None from Cloudinary
        # storage WITHOUT raising an exception - e.g. right after
        # a fresh upload, before Cloudinary has reported the
        # file's size back to Django. The old code only guarded
        # against an exception being raised, so a None size_bytes
        # slipped past the try/except and into
        # `size_bytes < 1024`, which throws
        # "'<' not supported between instances of 'NoneType' and
        # 'int'" - a 500 error on every resume upload. Guarding
        # against a falsy size_bytes (None or 0) as well fixes it.

        try:

            size_bytes = obj.file.size

        except Exception:

            return None

        if not size_bytes:

            return None

        if size_bytes < 1024:

            return f"{size_bytes} B"

        if size_bytes < 1024 * 1024:

            return f"{round(size_bytes / 1024)} KB"

        return f"{round(size_bytes / (1024*1024), 1)} MB"



class ResumeAnalysisSerializer(serializers.ModelSerializer):


    class Meta:

        model = ResumeAnalysis

        fields = [

            "id",

            "resume",

            "resume_score",

            "skills",

            "experience",

            "education",

            "certifications",

            "projects",

            "missing_information",

            "job_categories",

            "created_at",

        ]


        read_only_fields = [

            "created_at"

        ]


# =====================================================
# EXPERIENCE SERIALIZER
# =====================================================


class ExperienceSerializer(serializers.ModelSerializer):


    class Meta:


        model = Experience


        fields = "__all__"






# =====================================================
# STUDENT PROFILE CREATE / UPDATE SERIALIZER
# =====================================================


class StudentProfileUpdateSerializer(serializers.ModelSerializer):


    class Meta:


        model = StudentProfile


        fields = [

            "full_name",

            "student_id",

            "date_of_birth",

            "gender",

            "location",

            "institution",

            "course",

            "department",

            "graduation_year",

            "tenth_percentage",

            "twelfth_percentage",

            "diploma_details",

            "ug_cgpa",

            "pg_details",

            "backlog_count",

            "age",

            "skills",

            "certifications",

            "projects",

            "internships",

            "experience",

            "languages",

            "portfolio",

            "github",

            "linkedin",

            "preferred_location",

            "expected_salary",

            "career_interest",

        ]

        # =====================================================
# COMPANY PROFILE SERIALIZER
# =====================================================


class CompanyProfileSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    jobs = serializers.SerializerMethodField()





    class Meta:


        model = CompanyProfile


        fields = "__all__"






    def get_jobs(self,obj):


        jobs = obj.jobs.all()



        return JobSerializer(

            jobs,

            many=True

        ).data







# =====================================================
# COMPANY PROFILE UPDATE SERIALIZER
# =====================================================


class CompanyProfileUpdateSerializer(serializers.ModelSerializer):


    class Meta:


        model = CompanyProfile


        fields = [

            "company_name",

            "logo",

            "industry",

            "website",

            "description",

            "address",

            "company_size",

            "founded_year",

            "tagline",

            "vision",

            "mission",

            "contact_email",

            "phone",

            "linkedin",

            "twitter",

            "facebook",

            "instagram",

            "team_members",

        ]









# =====================================================
# JOB SERIALIZER
# =====================================================


class JobSerializer(serializers.ModelSerializer):


    company = serializers.CharField(
        source="company.company_name",
        read_only=True
    )


    job_type_display = serializers.CharField(
        source="get_job_type_display",
        read_only=True
    )


    work_mode_display = serializers.CharField(
        source="get_work_mode_display",
        read_only=True
    )


    class Meta:

        model = Job

        fields = [

            "id",
            "company",
            "title",
            "department",
            "description",
            "requirements",
            "skills_required",
            "qualification_required",
            "experience_required",
            "eligibility_criteria",
            "min_cgpa",
            "min_percentage",
            "eligible_departments",
            "eligible_graduation_years",
            "max_backlogs",
            "min_age",
            "max_age",
            "location",
            "salary",
            "job_type",
            "job_type_display",
            "work_mode",
            "work_mode_display",
            "vacancies",
            "application_deadline",
            "interview_process",
            "direct_apply_link",
            "status",
            "is_active",
            "created_at"

        ]



    def get_application_count(self,obj):

        return obj.applications.count()


# =====================================================
# JOB CREATE SERIALIZER
# =====================================================


class JobCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = Job


        fields = [

            "title",

            "department",

            "description",

            "requirements",

            "skills_required",

            "qualification_required",

            "experience_required",

            "min_cgpa",

            "min_percentage",

            "eligible_departments",

            "eligible_graduation_years",

            "max_backlogs",

            "min_age",

            "max_age",

            "location",

            "salary",

            "job_type",

            "work_mode",

            "vacancies",
              "application_deadline",

            "interview_process",

            "eligibility_criteria",


        ]








# =====================================================
# APPLICATION SERIALIZER
# =====================================================


class ApplicationSerializer(serializers.ModelSerializer):


    student = StudentProfileSerializer(

        read_only=True

    )


    job = JobSerializer(

        read_only=True

    )


    resume = ResumeSerializer(

        read_only=True

    )



    class Meta:


        model = Application


        fields = "__all__"








# =====================================================
# APPLICATION CREATE SERIALIZER
# =====================================================


class ApplicationCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = Application


        fields = [

            "job",

            "resume",

            "cover_letter"

        ]





# =====================================================
# APPLICATION STATUS UPDATE
# =====================================================


class ApplicationStatusSerializer(serializers.ModelSerializer):


    class Meta:


        model = Application


        fields = [

            "status"

        ]








# =====================================================
# CANDIDATE REVIEW SERIALIZER
# =====================================================


class CandidateReviewSerializer(serializers.ModelSerializer):


    application = ApplicationSerializer(

        read_only=True

    )



    recruiter = UserSerializer(

        read_only=True

    )



    class Meta:


        model = CandidateReview


        fields = "__all__"







# =====================================================
# CANDIDATE SHORTLIST SERIALIZER
# =====================================================


class CandidateShortlistSerializer(serializers.ModelSerializer):


    class Meta:


        model = CandidateReview


        fields = [

            "shortlisted",

            "rating",

            "remarks"

        ]









# =====================================================
# INTERVIEW SERIALIZER
# =====================================================


class InterviewSerializer(serializers.ModelSerializer):


    application = ApplicationSerializer(

        read_only=True

    )


    interviewer = UserSerializer(

        read_only=True

    )



    class Meta:


        model = Interview


        fields = "__all__"








# =====================================================
# INTERVIEW CREATE SERIALIZER
# =====================================================


class InterviewCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = Interview


        fields = [

            "application",

            "interview_date",

            "interview_mode",

            "meeting_link",

            "location"

        ]







# =====================================================
# INTERVIEW STATUS UPDATE
# =====================================================


class InterviewStatusSerializer(serializers.ModelSerializer):


    class Meta:


        model = Interview


        fields = [

            "status",

            "remarks"

        ]


        # =====================================================
# PLACEMENT DRIVE SERIALIZER
# =====================================================


class PlacementDriveSerializer(serializers.ModelSerializer):


    company = CompanyProfileSerializer(

        read_only=True

    )


    job_title = serializers.SerializerMethodField()


    company_name = serializers.SerializerMethodField()


    eligibility = serializers.CharField(

        source="eligibility_criteria",

        read_only=True,

        default=""

    )


    students = StudentProfileSerializer(

        many=True,

        read_only=True

    )


    created_by = UserSerializer(

        read_only=True

    )



    class Meta:


        model = PlacementDrive


        fields = "__all__"


    def get_job_title(self, obj):

        return obj.job.title if obj.job else obj.title


    def get_company_name(self, obj):

        return obj.company.company_name if obj.company else ""








# =====================================================
# PLACEMENT DRIVE CREATE SERIALIZER
# =====================================================


class PlacementDriveCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = PlacementDrive


        fields = [

            "title",

            "company",

            "job",

            "description",

            "eligibility_criteria",

            "drive_date",

            "registration_deadline",

            "vacancies",

            "selection_process",

            "venue",

            "meeting_link",

            "students",

            "status"

        ]


    def validate_drive_date(self, value):

        from django.utils import timezone

        # Only enforce "no past dates" when creating a new drive.
        # Editing other fields on an existing (already past) drive
        # should not be blocked just because its date is in the past.

        if value and self.instance is None and value < timezone.now().date():

            raise serializers.ValidationError(
                "Drive date cannot be in the past."
            )

        return value









# =====================================================
# NOTIFICATION SERIALIZER
# =====================================================


class NotificationSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    class Meta:


        model = Notification


        fields = "__all__"








# =====================================================
# NOTIFICATION CREATE SERIALIZER
# =====================================================


class NotificationCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = Notification


        fields = [

            "user",

            "title",

            "message",

            "notification_type"

        ]









# =====================================================
# CHAT CONVERSATION SERIALIZER
# =====================================================


class ChatConversationSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    class Meta:


        model = ChatConversation


        fields = "__all__"









# =====================================================
# CHAT MESSAGE SERIALIZER
# =====================================================


class ChatMessageSerializer(serializers.ModelSerializer):


    class Meta:


        model = ChatMessage


        fields = "__all__"









# =====================================================
# CHATBOT SETTINGS SERIALIZER
# =====================================================


class ChatbotSettingSerializer(serializers.ModelSerializer):


    class Meta:


        model = ChatbotSetting


        fields = "__all__"









# =====================================================
# WHATSAPP SETTINGS SERIALIZER
# =====================================================


class WhatsAppSettingSerializer(serializers.ModelSerializer):


    class Meta:


        model = WhatsAppSetting


        fields = "__all__"









# =====================================================
# WHATSAPP MESSAGE SERIALIZER
# =====================================================


class WhatsAppMessageSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    class Meta:


        model = WhatsAppMessage


        fields = "__all__"









# =====================================================
# SYSTEM SETTINGS SERIALIZER
# =====================================================


class SystemSettingSerializer(serializers.ModelSerializer):


    class Meta:


        model = SystemSetting


        fields = "__all__"








# =====================================================
# ADMIN SETTINGS SERIALIZER
# =====================================================


class AdminSettingSerializer(serializers.ModelSerializer):


    updated_by = UserSerializer(

        read_only=True

    )



    class Meta:


        model = AdminSetting


        fields = "__all__"


        # =====================================================
# AUDIT LOG SERIALIZER
# =====================================================


class AuditLogSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    class Meta:


        model = AuditLog


        fields = "__all__"









# =====================================================
# PLATFORM ANALYTICS SERIALIZER
# =====================================================


class PlatformAnalyticsSerializer(serializers.ModelSerializer):


    class Meta:


        model = PlatformAnalytics


        fields = "__all__"









# =====================================================
# CMS CONTENT SERIALIZER
# =====================================================


class CMSContentSerializer(serializers.ModelSerializer):


    class Meta:


        model = CMSContent


        fields = "__all__"









# =====================================================
# CUSTOM ROLE SERIALIZER
# =====================================================


class CustomRoleSerializer(serializers.ModelSerializer):


    permissions = PermissionSerializer(

        many=True,

        read_only=True

    )



    class Meta:


        model = CustomRole


        fields = "__all__"









# =====================================================
# LOGIN HISTORY SERIALIZER
# =====================================================


class LoginHistorySerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    class Meta:


        model = LoginHistory


        fields = "__all__"









# =====================================================
# SUPPORT TICKET SERIALIZER
# =====================================================


class SupportTicketSerializer(serializers.ModelSerializer):


    user = UserSerializer(

        read_only=True

    )



    assigned_to = UserSerializer(

        read_only=True

    )



    class Meta:


        model = SupportTicket


        fields = "__all__"









# =====================================================
# SUPPORT TICKET CREATE SERIALIZER
# =====================================================


class SupportTicketCreateSerializer(serializers.ModelSerializer):


    class Meta:


        model = SupportTicket


        fields = [

            "subject",

            "message"

        ]









# =====================================================
# SUPPORT STATUS UPDATE SERIALIZER
# =====================================================


class SupportTicketStatusSerializer(serializers.ModelSerializer):


    class Meta:


        model = SupportTicket


        fields = [

            "status"

        ]

class ResumeAnalysisSerializer(
    serializers.ModelSerializer
):


    class Meta:

        model = ResumeAnalysis

        fields="__all__"


# =====================================================
# SAVED JOB (student wishlist)
# =====================================================

from .models import SavedJob


class SavedJobSerializer(serializers.ModelSerializer):

    job = JobSerializer(
        read_only=True
    )

    class Meta:

        model = SavedJob

        fields = [
            "id",
            "job",
            "saved_at",
        ]


# =====================================================
# SCHEDULED PLACEMENT REPORTS
# =====================================================

from .models import ReportSchedule


class ReportScheduleSerializer(serializers.ModelSerializer):

    class Meta:

        model = ReportSchedule

        fields = [
            "id",
            "email",
            "frequency",
            "active",
            "last_sent_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "active",
            "last_sent_at",
            "created_at",
        ]
