from django.db import models 

from django.contrib.auth.models import AbstractUser

from django.utils import timezone

import os


def document_storage():
    """
    Storage for actual documents (resumes, PDFs, registration/GST
    certificates) - these need Cloudinary's 'raw' delivery type, not
    the 'image' type used by the default storage (set in settings.py),
    since Cloudinary treats non-image files differently. Passed as a
    callable (not called here) so Django evaluates it lazily at
    upload/access time rather than at import time - this avoids
    crashing at startup in local dev where Cloudinary isn't configured.
    """

    if os.getenv("CLOUDINARY_URL") or os.getenv("CLOUDINARY_CLOUD_NAME"):

        from cloudinary_storage.storage import RawMediaCloudinaryStorage

        return RawMediaCloudinaryStorage()

    from django.core.files.storage import FileSystemStorage

    return FileSystemStorage()





# =====================================================
# CUSTOM USER MODEL
# =====================================================


class User(AbstractUser):


    ROLE_CHOICES = (

        ("student", "Student"),

        ("company", "Company"),

        ("placement_admin",
         "Placement Administrator"),

        ("super_admin",
         "Super Admin"),

    )



    email = models.EmailField(

        unique=True

    )



    role = models.CharField(

        max_length=30,

        choices=ROLE_CHOICES,

        default="student"

    )



    phone = models.CharField(

        max_length=20,

        blank=True,

        null=True

    )



    whatsapp_number = models.CharField(

        max_length=20,

        blank=True,

        null=True

    )



    profile_image = models.ImageField(

        upload_to="profiles/",

        blank=True,

        null=True

    )



    is_verified = models.BooleanField(

        default=False

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )




    USERNAME_FIELD = "email"



    REQUIRED_FIELDS = [

        "username"

    ]





    def __str__(self):

        return self.email







# =====================================================
# PERMISSION MASTER
# =====================================================


class Permission(models.Model):


    name = models.CharField(

        max_length=150

    )



    code = models.CharField(

        max_length=150,

        unique=True

    )



    description = models.TextField(

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )




    def __str__(self):

        return self.name







# =====================================================
# ROLE PERMISSION MAPPING
# =====================================================


class RolePermission(models.Model):


    ROLE_CHOICES = (

        ("student","Student"),

        ("company","Company"),

        ("placement_admin",
         "Placement Administrator"),

        ("super_admin",
         "Super Admin"),

    )



    role = models.CharField(

        max_length=50,

        choices=ROLE_CHOICES

    )



    permission = models.ForeignKey(

        Permission,

        on_delete=models.CASCADE,

        related_name="role_permissions"

    )



    enabled = models.BooleanField(

        default=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )




    class Meta:


        unique_together = (

            "role",

            "permission"

        )




    def __str__(self):

        return f"{self.role} - {self.permission.name}"







# =====================================================
# STUDENT PROFILE
# =====================================================


class StudentProfile(models.Model):


    user = models.OneToOneField(

        User,

        on_delete=models.CASCADE,

        related_name="student_profile"

    )



    # =====================================================
    # PERSONAL INFORMATION
    # =====================================================


    full_name = models.CharField(

        max_length=200

    )


    student_id = models.CharField(

        max_length=100,

        unique=True,

        null=True,

        blank=True

    )


    date_of_birth = models.DateField(

        null=True,

        blank=True

    )


    gender = models.CharField(

        max_length=50,

        blank=True

    )


    location = models.TextField(

        blank=True

    )



    # =====================================================
    # ACADEMIC INFORMATION
    # =====================================================


    institution = models.CharField(

        max_length=200,

        blank=True

    )


    course = models.CharField(

        max_length=200,

        blank=True

    )


    department = models.CharField(

        max_length=200,

        blank=True

    )


    graduation_year = models.IntegerField(

        null=True,

        blank=True

    )


    tenth_percentage = models.FloatField(

        null=True,

        blank=True

    )


    twelfth_percentage = models.FloatField(

        null=True,

        blank=True

    )


    diploma_details = models.TextField(

        blank=True

    )


    ug_cgpa = models.FloatField(

        null=True,

        blank=True

    )


    pg_details = models.TextField(

        blank=True

    )



    # =====================================================
    # ELIGIBILITY DATA
    # =====================================================


    backlog_count = models.IntegerField(

        default=0

    )


    age = models.IntegerField(

        null=True,

        blank=True

    )



    # =====================================================
    # PROFESSIONAL INFORMATION
    # =====================================================


    skills = models.TextField(

        blank=True

    )


    certifications = models.TextField(

        blank=True

    )


    projects = models.TextField(

        blank=True

    )


    internships = models.TextField(

        blank=True

    )


    experience = models.TextField(

        blank=True

    )


    languages = models.TextField(

        blank=True

    )



    portfolio = models.URLField(

        blank=True

    )


    github = models.URLField(

        blank=True

    )


    linkedin = models.URLField(

        blank=True

    )



    # =====================================================
    # RESUME MANAGEMENT
    # =====================================================


    resume = models.FileField(

        upload_to="student/resume/",

        storage=document_storage,

        null=True,

        blank=True

    )


    resume_score = models.IntegerField(

        default=0

    )



    # =====================================================
    # JOB PREFERENCE (AI MATCHING)
    # =====================================================


    preferred_location = models.CharField(

        max_length=200,

        blank=True

    )


    expected_salary = models.CharField(

        max_length=100,

        blank=True

    )


    career_interest = models.TextField(

        blank=True

    )



    # =====================================================
    # PROFILE STATUS
    # =====================================================


    profile_completion = models.IntegerField(

        default=0

    )


    verified = models.BooleanField(

        default=False

    )


    PLACEMENT_STATUS_CHOICES = (

        ("Looking", "Looking"),

        ("Placed", "Placed"),

        ("Not Placed", "Not Placed"),

    )

    placement_status = models.CharField(

        max_length=20,

        choices=PLACEMENT_STATUS_CHOICES,

        default="Looking",

    )


    created_at = models.DateTimeField(

        auto_now_add=True

    )


    updated_at = models.DateTimeField(

        auto_now=True

    )




    def __str__(self):

        return self.full_name


    def calculate_profile_completion(self):
        """
        Weighs a fixed set of the most meaningful profile fields
        equally and returns a 0-100 percentage of how many are
        actually filled in. Recalculated on every save() below,
        so it always reflects what's genuinely on the profile
        instead of a value frozen at registration time.
        """

        fields_to_check = [
            self.full_name,
            self.student_id,
            self.date_of_birth,
            self.gender,
            self.location,
            self.institution,
            self.course,
            self.department,
            self.graduation_year,
            self.ug_cgpa,
            self.skills,
            self.projects,
            bool(self.resume),
            self.preferred_location,
            self.linkedin,
        ]

        filled = sum(1 for f in fields_to_check if f not in (None, "", 0, False))

        return round((filled / len(fields_to_check)) * 100)

    def save(self, *args, **kwargs):

        # student_id has unique=True but is optional and not
        # collected on the registration form. Left alone,
        # Django saves an unset CharField as "" (empty string),
        # not NULL - and unique=True still blocks *duplicate
        # empty strings*, even though it correctly allows
        # unlimited NULLs. That meant the second student to
        # register ever would collide with the first and fail
        # registration entirely. Normalizing "" to None here
        # closes this off for every code path that creates or
        # updates a StudentProfile, not just one view.

        if self.student_id == "":

            self.student_id = None

        # profile_completion used to be hardcoded to 20 at
        # registration and never recalculated afterward, no
        # matter how much of the profile got filled in later.
        # Recalculating it here means every save - registration,
        # the student's own profile edit, or a placement admin
        # edit - keeps it accurate.

        self.profile_completion = self.calculate_profile_completion()

        super().save(*args, **kwargs)


# =====================================================
# COMPANY PROFILE
# =====================================================


class CompanyProfile(models.Model):


    user = models.OneToOneField(

        User,

        on_delete=models.CASCADE,

        related_name="company_profile"

    )



    company_name = models.CharField(

        max_length=200

    )



    logo = models.ImageField(

        upload_to="company/logo/",

        blank=True,

        null=True

    )



    industry = models.CharField(

        max_length=200,

        blank=True

    )



    website = models.URLField(

        blank=True

    )



    description = models.TextField(

        blank=True

    )



    address = models.TextField(

        blank=True

    )


    verified = models.BooleanField(

        default=False

    )


    # -------------------------------------------------
    # About Company
    # -------------------------------------------------

    company_size = models.CharField(

        max_length=50,

        blank=True

    )


    founded_year = models.CharField(

        max_length=10,

        blank=True

    )


    tagline = models.CharField(

        max_length=255,

        blank=True

    )


    vision = models.TextField(

        blank=True

    )


    mission = models.TextField(

        blank=True

    )


    # -------------------------------------------------
    # Contact Information
    # -------------------------------------------------

    contact_email = models.EmailField(

        blank=True

    )


    phone = models.CharField(

        max_length=30,

        blank=True

    )


    hr_contact_name = models.CharField(

        max_length=150,

        blank=True,

        help_text="Name of the HR/recruiting contact person.",

    )


    company_type = models.CharField(

        max_length=50,

        blank=True,

        help_text="e.g. Startup, MNC, SME, Government",

    )


    # -------------------------------------------------
    # Social Media
    # -------------------------------------------------

    linkedin = models.URLField(

        blank=True

    )


    twitter = models.URLField(

        blank=True

    )


    facebook = models.URLField(

        blank=True

    )


    instagram = models.URLField(

        blank=True

    )


    # -------------------------------------------------
    # Team Members
    # e.g. [{"name":"Monika","role":"HR Manager","email":"..."}]
    # -------------------------------------------------

    team_members = models.JSONField(

        default=list,

        blank=True

    )


    # -------------------------------------------------
    # Registration approval workflow
    # -------------------------------------------------

    APPROVAL_STATUS_CHOICES = (
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    approval_status = models.CharField(

        max_length=20,

        choices=APPROVAL_STATUS_CHOICES,

        default="pending",

        help_text="Company cannot log in until this is 'approved'."

    )

    rejection_reason = models.TextField(

        blank=True,

        help_text="Shown to the company if their application is rejected."

    )

    registration_document = models.FileField(

        upload_to="company/documents/registration/",

        storage=document_storage,

        null=True,

        blank=True

    )

    gst_document = models.FileField(

        upload_to="company/documents/gst/",

        storage=document_storage,

        null=True,

        blank=True

    )


    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )




    def __str__(self):

        return self.company_name



class CompanyRegistrationPhoto(models.Model):

    company = models.ForeignKey(

        CompanyProfile,

        on_delete=models.CASCADE,

        related_name="registration_photos"

    )

    photo = models.ImageField(

        upload_to="company/documents/photos/"

    )

    uploaded_at = models.DateTimeField(

        auto_now_add=True

    )

    def __str__(self):

        return f"Photo for {self.company.company_name}"







# =====================================================
# PLACEMENT ADMIN PROFILE
# =====================================================


class PlacementAdminProfile(models.Model):


    user = models.OneToOneField(

        User,

        on_delete=models.CASCADE,

        related_name="placement_admin_profile"

    )



    full_name = models.CharField(

        max_length=200

    )



    department = models.CharField(

        max_length=200,

        blank=True

    )



    designation = models.CharField(

        max_length=100,

        default="Placement Administrator"

    )



    verified = models.BooleanField(

        default=False

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.full_name

    # =====================================================
# STUDENT EDUCATION
# =====================================================


class Education(models.Model):


    student = models.ForeignKey(

        StudentProfile,

        on_delete=models.CASCADE,

        related_name="education_details"

    )



    qualification = models.CharField(

        max_length=200

    )



    institution = models.CharField(

        max_length=200

    )



    specialization = models.CharField(

        max_length=200,

        blank=True

    )



    start_year = models.CharField(

        max_length=10,

        blank=True

    )



    end_year = models.CharField(

        max_length=10,

        blank=True

    )



    grade = models.CharField(

        max_length=50,

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )




    def __str__(self):

        return self.qualification








# =====================================================
# STUDENT SKILLS
# =====================================================


class Skill(models.Model):


    student = models.ForeignKey(

        StudentProfile,

        on_delete=models.CASCADE,

        related_name="skills_list"

    )



    name = models.CharField(

        max_length=100

    )



    proficiency = models.CharField(

        max_length=50,

        choices=(

            ("beginner","Beginner"),

            ("intermediate","Intermediate"),

            ("advanced","Advanced"),

            ("expert","Expert"),

        ),

        default="beginner"

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )




    def __str__(self):

        return self.name







# =====================================================
# STUDENT RESUME
# =====================================================


from django.db import models
from django.conf import settings
import os


def resume_upload_path(instance, filename):

    return f"resumes/{instance.student.id}/{filename}"


class Resume(models.Model):

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_resumes"
    )


    # Resume File

    file = models.FileField(
        upload_to=resume_upload_path,
        storage=document_storage
    )


    filename = models.CharField(
        max_length=255
    )


    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    # Active resume
    # Only latest uploaded resume is active

    is_active = models.BooleanField(
        default=True
    )


    # =====================
    # AI Resume Analysis
    # =====================


    resume_score = models.IntegerField(
        default=0
    )


    skills = models.JSONField(
        default=list,
        blank=True
    )


    experience = models.JSONField(
        default=list,
        blank=True
    )


    education = models.JSONField(
        default=list,
        blank=True
    )


    certifications = models.JSONField(
        default=list,
        blank=True
    )


    projects = models.JSONField(
        default=list,
        blank=True
    )


    missing_information = models.JSONField(
        default=list,
        blank=True
    )


    job_categories = models.JSONField(
        default=list,
        blank=True
    )


    extracted_text = models.TextField(
        blank=True,
        null=True
    )


    class Meta:

        ordering = [
            "-uploaded_at"
        ]


    def __str__(self):

        return f"{self.student.username} Resume"


    def delete_file(self):

        # file.delete() goes through Django's Storage API, so it
        # works the same way whether the file lives on local disk
        # or in Cloudinary (this project uses
        # RawMediaCloudinaryStorage for resumes - see
        # document_storage() at the top of this file).
        # os.path.isfile()/os.remove() only work for local disk
        # storage and raise NotImplementedError under Cloudinary,
        # which broke every resume deletion in production.

        if self.file:

            self.file.delete(save=False)


class ResumeAnalysisHistory(models.Model):

    resume = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        related_name="analysis_history"
    )


    analyzed_at = models.DateTimeField(
        auto_now_add=True
    )


    ai_model = models.CharField(
        max_length=100,
        default="Groq AI"
    )


    response_time = models.FloatField(
        default=0
    )


    def __str__(self):

        return (
            f"Analysis {self.resume}"
        )             


# =====================================================
# STUDENT EXPERIENCE
# =====================================================


class Experience(models.Model):


    student = models.ForeignKey(

        StudentProfile,

        on_delete=models.CASCADE,

        related_name="experience_details"

    )



    company_name = models.CharField(

        max_length=200

    )



    designation = models.CharField(

        max_length=200

    )



    description = models.TextField(

        blank=True

    )



    start_date = models.DateField(

        null=True,

        blank=True

    )



    end_date = models.DateField(

        null=True,

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )




    def __str__(self):

        return self.designation







# =====================================================
# COMPANY JOB MODEL
# =====================================================


class Job(models.Model):


    STATUS_CHOICES = (

        ("pending", "Pending"),

        ("active", "Active"),

        ("closed", "Closed"),

        ("rejected", "Rejected"),

    )



    WORK_MODE_CHOICES = (

        ("onsite", "On Site"),

        ("remote", "Remote"),

        ("hybrid", "Hybrid"),

    )



    JOB_TYPE_CHOICES = (

        ("full_time", "Full Time"),

        ("part_time", "Part Time"),

        ("internship", "Internship"),

        ("contract", "Contract"),

    )




    # ================================
    # COMPANY
    # ================================


    company = models.ForeignKey(

        CompanyProfile,

        on_delete=models.CASCADE,

        related_name="jobs"

    )




    # ================================
    # BASIC INFORMATION
    # ================================


    title = models.CharField(

        max_length=200

    )


    department = models.CharField(

        max_length=100,

        blank=True

    )



    description = models.TextField()




    # ================================
    # REQUIREMENTS
    # ================================


    requirements = models.TextField(

        blank=True,

        help_text="Job requirements"

    )



    skills_required = models.TextField(

        blank=True,

        help_text="Required technical skills"

    )



    qualification_required = models.CharField(

        max_length=200,

        blank=True

    )



    experience_required = models.CharField(

        max_length=100,

        blank=True

    )




    eligibility_criteria = models.TextField(

        blank=True,

        help_text="Student eligibility requirements"

    )


    # -------------------------------------------------
    # Structured eligibility conditions (used by the
    # Eligibility Engine to compute a real Eligible /
    # Not Eligible result, instead of free-text alone).
    # Every field is optional - a blank/null field means
    # "no restriction" for that condition.
    # -------------------------------------------------

    min_cgpa = models.FloatField(

        null=True,

        blank=True,

        help_text="Minimum CGPA (out of 10) required"

    )


    min_percentage = models.FloatField(

        null=True,

        blank=True,

        help_text="Minimum 10th/12th percentage required"

    )


    eligible_departments = models.CharField(

        max_length=255,

        blank=True,

        help_text="Comma-separated departments, blank = all"

    )


    eligible_graduation_years = models.CharField(

        max_length=255,

        blank=True,

        help_text="Comma-separated graduation years, blank = any"

    )


    max_backlogs = models.IntegerField(

        null=True,

        blank=True,

        help_text="Maximum allowed active backlogs, blank = no limit"

    )


    min_age = models.IntegerField(

        null=True,

        blank=True

    )


    max_age = models.IntegerField(

        null=True,

        blank=True

    )





    # ================================
    # JOB DETAILS
    # ================================


    location = models.CharField(

        max_length=200

    )




    salary = models.CharField(

        max_length=100,

        blank=True

    )





    job_type = models.CharField(

        max_length=100,

        choices=JOB_TYPE_CHOICES,

        default="full_time"

    )





    work_mode = models.CharField(

        max_length=50,

        choices=WORK_MODE_CHOICES,

        default="onsite"

    )





    vacancies = models.IntegerField(

        default=1

    )





    # ================================
    # APPLICATION DETAILS
    # ================================


    application_deadline = models.DateField(

        null=True,

        blank=True

    )





    interview_process = models.TextField(

        blank=True,

        help_text="Example: Technical Round + HR Interview"

    )





    # ================================
    # STATUS
    # ================================


    status = models.CharField(

        max_length=20,

        choices=STATUS_CHOICES,

        default="pending"

    )





    is_active = models.BooleanField(

        default=True

    )





    # ================================
    # TIMESTAMPS
    # ================================


    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )


    # -------------------------------------------------
    # Optional external application link. When set, the
    # student Job Details page shows a "Direct Apply"
    # button that opens this URL instead of (or alongside)
    # the in-platform application flow. Managed from the
    # Django admin backend ("placement administrator") or
    # by the company when posting/editing the job.
    # -------------------------------------------------

    direct_apply_link = models.URLField(

        blank=True,

        null=True

    )





    def __str__(self):

        return self.title



    # =====================================================
# JOB APPLICATION
# =====================================================


class Application(models.Model):


    STATUS_CHOICES = (

        ("applied","Applied"),

        ("reviewing","Under Review"),

        ("shortlisted","Shortlisted"),

        ("interview","Interview Scheduled"),

        ("selected","Selected"),

        ("rejected","Rejected"),

        ("withdrawn","Withdrawn"),

    )



    student = models.ForeignKey(

        StudentProfile,

        on_delete=models.CASCADE,

        related_name="applications"

    )



    job = models.ForeignKey(

        Job,

        on_delete=models.CASCADE,

        related_name="applications"

    )



    resume = models.ForeignKey(

        Resume,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="applications"

    )



    cover_letter = models.TextField(

        blank=True

    )



    status = models.CharField(

        max_length=30,

        choices=STATUS_CHOICES,

        default="applied"

    )



    applied_date = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )



    updated_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="application_updates"

    )


    recruiter_notes = models.TextField(

        blank=True,

        help_text="Private notes visible only to the hiring company"

    )




    class Meta:

        unique_together = (

            "student",

            "job"

        )




    def __str__(self):

        return (

            self.student.full_name

            +

            " - "

            +

            self.job.title

        )









# =====================================================
# CANDIDATE REVIEW
# =====================================================


class CandidateReview(models.Model):


    application = models.ForeignKey(

        Application,

        on_delete=models.CASCADE,

        related_name="candidate_reviews"

    )



    recruiter = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="candidate_reviews"

    )



    rating = models.IntegerField(

        default=0

    )



    shortlisted = models.BooleanField(

        default=False

    )



    remarks = models.TextField(

        blank=True

    )



    reviewed_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )




    def __str__(self):

        return (

            self.application.job.title

            +

            " review"

        )









# =====================================================
# INTERVIEW SCHEDULING
# =====================================================


class Interview(models.Model):


    MODE_CHOICES = (

        ("online","Online"),

        ("physical","Physical"),

        ("phone","Phone"),

    )



    STATUS_CHOICES = (

        ("scheduled","Scheduled"),

        ("completed","Completed"),

        ("cancelled","Cancelled"),

        ("rescheduled","Rescheduled"),

    )



    application = models.ForeignKey(

        Application,

        on_delete=models.CASCADE,

        related_name="interviews"

    )



    interviewer = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        related_name="conducted_interviews"

    )



    interview_date = models.DateTimeField()



    interview_mode = models.CharField(

        max_length=50,

        choices=MODE_CHOICES,

        default="online"

    )



    meeting_link = models.URLField(

        blank=True

    )



    location = models.CharField(

        max_length=255,

        blank=True

    )



    status = models.CharField(

        max_length=50,

        choices=STATUS_CHOICES,

        default="scheduled"

    )



    remarks = models.TextField(

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return (

            self.application.student.full_name

            +

            " Interview"

        )









# =====================================================
# PLACEMENT DRIVE
# =====================================================


class PlacementDrive(models.Model):


    STATUS_CHOICES = (

        ("upcoming","Upcoming"),

        ("ongoing","Ongoing"),

        ("completed","Completed"),

        ("cancelled","Cancelled"),

    )



    title = models.CharField(

        max_length=200

    )



    company = models.ForeignKey(

        CompanyProfile,

        on_delete=models.CASCADE,

        related_name="placement_drives"

    )


    job = models.ForeignKey(

        Job,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="placement_drives"

    )


    registration_deadline = models.DateField(

        null=True,

        blank=True

    )


    vacancies = models.IntegerField(

        null=True,

        blank=True

    )


    selection_process = models.CharField(

        max_length=255,

        blank=True,

        help_text="e.g. Aptitude Test, Technical Interview, HR Interview"

    )


    meeting_link = models.URLField(

        blank=True,

        help_text="Online meeting link, if the drive is virtual"

    )



    description = models.TextField(

        blank=True

    )



    eligibility_criteria = models.TextField(

        blank=True

    )



    drive_date = models.DateField()



    venue = models.CharField(

        max_length=255,

        blank=True

    )



    students = models.ManyToManyField(

        StudentProfile,

        blank=True,

        related_name="placement_drives"

    )



    status = models.CharField(

        max_length=30,

        choices=STATUS_CHOICES,

        default="upcoming"

    )



    created_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        related_name="created_drives"

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.title

# =====================================================
# NOTIFICATION SYSTEM
# =====================================================


class Notification(models.Model):


    TYPE_CHOICES = (

        ("job","Job Update"),

        ("application","Application Update"),

        ("interview","Interview"),

        ("placement","Placement Drive"),

        ("system","System"),

    )



    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="notifications"

    )



    title = models.CharField(

        max_length=200

    )



    message = models.TextField()



    notification_type = models.CharField(

        max_length=50,

        choices=TYPE_CHOICES,

        default="system"

    )



    is_read = models.BooleanField(

        default=False

    )



    whatsapp_sent = models.BooleanField(

        default=False

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    class Meta:

        ordering = [

            "-created_at"

        ]





    def __str__(self):

        return self.title







# =====================================================
# AI CHATBOT CONVERSATION
# =====================================================


class ChatConversation(models.Model):


    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="chat_sessions",

        null=True,

        blank=True

    )



    session_id = models.CharField(

        max_length=255,

        unique=True

    )



    started_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.session_id









# =====================================================
# AI CHATBOT MESSAGES
# =====================================================


class ChatMessage(models.Model):


    SENDER_CHOICES = (

        ("user","User"),

        ("bot","AI Bot"),

    )



    conversation = models.ForeignKey(

        ChatConversation,

        on_delete=models.CASCADE,

        related_name="messages"

    )



    sender = models.CharField(

        max_length=20,

        choices=SENDER_CHOICES

    )



    message = models.TextField()



    created_at = models.DateTimeField(

        auto_now_add=True

    )





    class Meta:

        ordering=[

            "created_at"

        ]





    def __str__(self):

        return f"{self.sender}: {self.message[:50]}"









# =====================================================
# AI CHATBOT CONFIGURATION
# =====================================================


class ChatbotSetting(models.Model):


    name = models.CharField(

        max_length=100,

        default="Vetri Career Assistant"

    )



    system_prompt = models.TextField(

        blank=True

    )



    welcome_message = models.TextField(

        default=

        "Hi, I am Vetri Jobs Career Assistant"

    )



    enabled = models.BooleanField(

        default=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.name







# =====================================================
# WHATSAPP CONFIGURATION
# =====================================================


class WhatsAppSetting(models.Model):


    provider_name = models.CharField(

        max_length=100,

        default="WhatsApp Business API"

    )



    phone_number_id = models.CharField(

        max_length=200

    )



    access_token = models.TextField()


    verify_token = models.CharField(

        max_length=100,

        default="vetrijobs",

        help_text="Set this exact value as the 'Verify Token' when "
                  "configuring the webhook in Meta's WhatsApp Business "
                  "Platform dashboard.",

    )




    enabled = models.BooleanField(

        default=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.provider_name







# =====================================================
# WHATSAPP MESSAGE LOG
# =====================================================


class WhatsAppMessage(models.Model):


    STATUS_CHOICES = (

        ("pending","Pending"),

        ("sent","Sent"),

        ("failed","Failed"),

    )



    user = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="whatsapp_messages"

    )



    phone_number = models.CharField(

        max_length=20

    )



    message = models.TextField()



    status = models.CharField(

        max_length=20,

        choices=STATUS_CHOICES,

        default="pending"

    )



    provider_response = models.TextField(

        blank=True,

        null=True

    )



    sent_at = models.DateTimeField(

        null=True,

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )





    def __str__(self):

        return self.phone_number







# =====================================================
# SYSTEM SETTINGS
# =====================================================


class SystemSetting(models.Model):


    key = models.CharField(

        max_length=100,

        unique=True

    )



    value = models.TextField()



    description = models.TextField(

        blank=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.key


    # =====================================================
# AUDIT LOG SYSTEM
# =====================================================


class AuditLog(models.Model):


    ACTION_CHOICES = (

        ("create","Create"),

        ("update","Update"),

        ("delete","Delete"),

        ("login","Login"),

        ("logout","Logout"),

        ("permission","Permission Change"),

    )



    user = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="audit_logs"

    )



    action = models.CharField(

        max_length=50,

        choices=ACTION_CHOICES

    )



    module = models.CharField(

        max_length=100

    )



    description = models.TextField()



    ip_address = models.GenericIPAddressField(

        null=True,

        blank=True

    )



    user_agent = models.TextField(

        blank=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )





    class Meta:

        ordering = [

            "-created_at"

        ]





    def __str__(self):

        return (

            str(self.user)

            +

            " - "

            +

            self.action

        )









# =====================================================
# PLATFORM ANALYTICS
# =====================================================


class PlatformAnalytics(models.Model):


    date = models.DateField(

        default=timezone.now

    )



    total_students = models.IntegerField(

        default=0

    )



    total_companies = models.IntegerField(

        default=0

    )



    total_jobs = models.IntegerField(

        default=0

    )



    total_applications = models.IntegerField(

        default=0

    )



    total_selected_students = models.IntegerField(

        default=0

    )



    total_interviews = models.IntegerField(

        default=0

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )





    class Meta:

        ordering = [

            "-date"

        ]





    def __str__(self):

        return str(self.date)









# =====================================================
# WEBSITE / CMS MANAGEMENT
# =====================================================


class CMSContent(models.Model):


    CONTENT_TYPE = (

        ("banner","Banner"),

        ("announcement","Announcement"),

        ("about","About"),

        ("faq","FAQ"),

    )



    title = models.CharField(

        max_length=200

    )



    content_type = models.CharField(

        max_length=50,

        choices=CONTENT_TYPE

    )



    content = models.TextField()



    image = models.ImageField(

        upload_to="cms/",

        blank=True,

        null=True

    )



    is_active = models.BooleanField(

        default=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.title









# =====================================================
# ADMIN SYSTEM SETTINGS
# =====================================================


class AdminSetting(models.Model):


    CATEGORY_CHOICES = (

        ("general","General"),

        ("security","Security"),

        ("email","Email"),

        ("notification","Notification"),

        ("integration","Integration"),

    )



    category = models.CharField(

        max_length=50,

        choices=CATEGORY_CHOICES

    )



    key = models.CharField(

        max_length=100,

        unique=True

    )



    value = models.TextField()



    description = models.TextField(

        blank=True

    )



    updated_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.key







# =====================================================
# ROLE CREATION MANAGEMENT
# SUPER ADMIN CAN MANAGE ROLES
# =====================================================


class CustomRole(models.Model):


    name = models.CharField(

        max_length=100,

        unique=True

    )



    code = models.CharField(

        max_length=100,

        unique=True

    )



    description = models.TextField(

        blank=True

    )



    permissions = models.ManyToManyField(

        Permission,

        blank=True

    )



    is_active = models.BooleanField(

        default=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )





    def __str__(self):

        return self.name







# =====================================================
# USER LOGIN HISTORY
# =====================================================


class LoginHistory(models.Model):


    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="login_history"

    )



    login_time = models.DateTimeField(

        auto_now_add=True

    )



    logout_time = models.DateTimeField(

        null=True,

        blank=True

    )



    ip_address = models.GenericIPAddressField(

        null=True,

        blank=True

    )



    device = models.CharField(

        max_length=200,

        blank=True

    )





    def __str__(self):

        return str(self.user)







# =====================================================
# SUPPORT / CONTACT REQUEST
# =====================================================


class SupportTicket(models.Model):


    STATUS = (

        ("open","Open"),

        ("processing","Processing"),

        ("resolved","Resolved"),

        ("closed","Closed"),

    )



    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE

    )



    subject = models.CharField(

        max_length=200

    )



    message = models.TextField()



    status = models.CharField(

        max_length=30,

        choices=STATUS,

        default="open"

    )



    assigned_to = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name="assigned_tickets"

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    updated_at = models.DateTimeField(

        auto_now=True

    )





    def __str__(self):

        return self.subject

# =====================================================
# CMS NAVBAR
# =====================================================


class Navbar(models.Model):


    title = models.CharField(

        max_length=100

    )


    url = models.CharField(

        max_length=255,

        blank=True,

        null=True

    )


    order = models.IntegerField(

        default=0

    )


    is_active = models.BooleanField(

        default=True

    )


    created_at = models.DateTimeField(

        auto_now_add=True

    )



    class Meta:

        ordering = [

            "order"

        ]



    def __str__(self):

        return self.title






# =====================================================
# CMS FOOTER
# =====================================================


class Footer(models.Model):


    title = models.CharField(

        max_length=100

    )


    content = models.TextField()



    is_active = models.BooleanField(

        default=True

    )



    created_at = models.DateTimeField(

        auto_now_add=True

    )



    def __str__(self):

        return self.title






# =====================================================
# HOME PAGE CONTENT
# =====================================================


class Home(models.Model):


    title = models.CharField(

        max_length=200

    )


    subtitle = models.TextField(

        blank=True

    )


    image = models.ImageField(

        upload_to="home/",

        blank=True,

        null=True

    )


    button_text = models.CharField(

        max_length=100,

        blank=True

    )


    button_link = models.CharField(

        max_length=255,

        blank=True

    )


    is_active = models.BooleanField(

        default=True

    )


    created_at = models.DateTimeField(

        auto_now_add=True

    )



    def __str__(self):

        return self.title


    # =====================================================
# STUDENT RESUME MODEL
# =====================================================


class StudentResume(models.Model):


    student = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="resumes"

    )


    resume = models.FileField(

        upload_to="student/resumes/",

        storage=document_storage

    )


    file_name = models.CharField(

        max_length=255,

        blank=True

    )


    version = models.IntegerField(

        default=1

    )


    uploaded_at = models.DateTimeField(

        auto_now_add=True

    )



    is_active = models.BooleanField(

        default=True

    )




    def save(self,*args,**kwargs):


        if self.resume:

            self.file_name = self.resume.name


        super().save(*args,**kwargs)





    def __str__(self):

        return self.file_name

class ResumeAnalysis(models.Model):

    resume = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        related_name="analysis"
    )


    skills = models.JSONField(default=list)

    experience = models.JSONField(default=list)

    education = models.JSONField(default=list)

    certifications = models.JSONField(default=list)

    projects = models.JSONField(default=list)

    missing_information = models.JSONField(default=list)

    job_categories = models.JSONField(default=list)


    resume_score = models.IntegerField(
        default=0
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):

        return f"{self.resume.title} Analysis"

# =====================================================
# SAVED / BOOKMARKED JOBS (student wishlist)
# =====================================================

class SavedJob(models.Model):

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="saved_jobs"
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="saved_by"
    )

    saved_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        unique_together = (
            "student",
            "job"
        )

        ordering = ["-saved_at"]

    def __str__(self):

        return f"{self.student} saved {self.job.title}"


# =====================================================
# CHATBOT KNOWLEDGE BASE
# Editable placement policies / FAQs / guidelines that the
# AI chatbot draws on, without needing any code changes.
# =====================================================

class KnowledgeBaseEntry(models.Model):

    CATEGORY_CHOICES = (
        ("policy", "Placement Policy"),
        ("faq", "FAQ"),
        ("company", "Company Information"),
        ("job", "Job Information"),
        ("procedure", "Placement Procedure"),
        ("guideline", "Student Guideline"),
        ("interview", "Interview Instructions"),
        ("resume", "Resume Guidelines"),
        ("career", "Career Resource"),
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="faq",
    )

    title = models.CharField(
        max_length=255,
    )

    content = models.TextField()

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["category", "title"]

    def __str__(self):
        return f"[{self.category}] {self.title}"


# =====================================================
# ADMIN CONTROLS (Requirement 28)
# Configurable master lists the Super Admin manages from
# Django Admin, which the rest of the platform (dropdowns,
# forms, filters) reads from - so changing them here
# actually changes what students/companies see, with no
# code changes needed.
# =====================================================


class Department(models.Model):

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Short code, e.g. CSE, ECE",
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Course(models.Model):

    name = models.CharField(
        max_length=150,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )

    duration_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "department")

    def __str__(self):
        return self.name


class JobCategory(models.Model):

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Job categories"

    def __str__(self):
        return self.name


class NotificationTemplate(models.Model):

    EVENT_CHOICES = (
        ("application_status", "Application Status Changed"),
        ("interview_scheduled", "Interview Scheduled"),
        ("drive_created", "New Placement Drive"),
        ("job_posted", "New Job Posted"),
        ("profile_verified", "Profile Verified"),
        ("custom", "Custom / Manual"),
    )

    name = models.CharField(
        max_length=150,
    )

    event = models.CharField(
        max_length=30,
        choices=EVENT_CHOICES,
        default="custom",
    )

    subject = models.CharField(
        max_length=255,
        blank=True,
    )

    body = models.TextField(
        help_text="Use {student_name}, {job_title}, {company_name}, "
                   "{status}, {interview_date} as placeholders.",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["event", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_event_display()})"


class WhatsAppTemplate(models.Model):

    EVENT_CHOICES = NotificationTemplate.EVENT_CHOICES

    name = models.CharField(
        max_length=150,
    )

    event = models.CharField(
        max_length=30,
        choices=EVENT_CHOICES,
        default="custom",
    )

    message = models.TextField(
        help_text="Use {student_name}, {job_title}, {company_name}, "
                   "{status}, {interview_date} as placeholders.",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["event", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_event_display()})"


# =====================================================
# PLACEMENT QUERY (chatbot actions: raise a query,
# request an interview slot)
# =====================================================

class PlacementQuery(models.Model):

    CATEGORY_CHOICES = (
        ("general", "General Query"),
        ("interview_request", "Interview Slot Request"),
        ("application", "Application Query"),
        ("resume", "Resume Query"),
        ("technical", "Technical Issue"),
    )

    STATUS_CHOICES = (
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="placement_queries",
        null=True,
        blank=True,
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="general",
    )

    message = models.TextField()

    related_application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
    )

    source = models.CharField(
        max_length=20,
        default="chatbot",
        help_text="Where this query came from (chatbot, form, etc.)",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Placement queries"

    def __str__(self):
        return f"{self.student} - {self.get_category_display()}"


# =====================================================
# SITE BRANDING (logo managed from Django Admin, read by
# the frontend so uploading a new logo here updates it
# everywhere on the site automatically)
# =====================================================

class SiteBranding(models.Model):

    site_name = models.CharField(
        max_length=100,
        default="Vetri Jobs",
    )

    tagline = models.CharField(
        max_length=150,
        default="Career Portal",
        blank=True,
    )

    logo = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Shown in the navbar/sidebar across the whole site "
                  "instead of the default text badge.",
    )

    favicon = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
    )


    # -------------------------------------------------
    # Auth page hero images/copy (Student Login/Register
    # split-screen design). All optional - each page falls
    # back to a built-in illustration if nothing is uploaded,
    # so the site never looks broken with these left blank.
    # -------------------------------------------------

    login_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Student Login page.",
    )

    login_headline = models.CharField(
        max_length=100,
        default="Learn Apply Grow",
        blank=True,
    )

    login_subheadline = models.CharField(
        max_length=200,
        default="AI-powered placement platform connecting students "
                "with top opportunities.",
        blank=True,
    )

    register_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Student Register page.",
    )

    register_headline = models.CharField(
        max_length=100,
        default="Your Future Starts Here",
        blank=True,
    )

    register_subheadline = models.CharField(
        max_length=200,
        default="Join thousands of students and discover your dream career.",
        blank=True,
    )


    # -------------------------------------------------
    # Company Login/Register hero images/copy - same idea
    # as the student pages above, independently configurable.
    # -------------------------------------------------

    company_login_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Company Login page.",
    )

    company_login_headline = models.CharField(
        max_length=100,
        default="Hire Top Talent Build Tomorrow",
        blank=True,
    )

    company_login_subheadline = models.CharField(
        max_length=200,
        default="Connect with skilled students and grow your team.",
        blank=True,
    )

    company_register_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Company Register page.",
    )

    company_register_headline = models.CharField(
        max_length=100,
        default="Let's Build a Better Tomorrow",
        blank=True,
    )

    company_register_subheadline = models.CharField(
        max_length=200,
        default="Create your company account and start hiring the "
                "right talent.",
        blank=True,
    )


    # -------------------------------------------------
    # Placement Admin Login hero image/copy.
    # -------------------------------------------------

    placement_login_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Placement Admin Login page.",
    )

    placement_login_headline = models.CharField(
        max_length=100,
        default="Manage Placements Create Impact",
        blank=True,
    )

    placement_login_subheadline = models.CharField(
        max_length=200,
        default="Streamline drives, track progress and empower "
                "student success.",
        blank=True,
    )


    # -------------------------------------------------
    # Super Admin Login hero image/copy.
    # -------------------------------------------------

    admin_login_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Left-panel image on the Super Admin Login page.",
    )

    admin_login_headline = models.CharField(
        max_length=100,
        default="Complete Control Total Visibility",
        blank=True,
    )

    admin_login_subheadline = models.CharField(
        max_length=200,
        default="Manage every user, role and setting across the "
                "whole platform.",
        blank=True,
    )


    # -------------------------------------------------
    # Student Dashboard "AI Career Assistant" card image.
    # -------------------------------------------------

    dashboard_assistant_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Illustration shown in the AI Career Assistant card "
                  "on the Student Dashboard.",
    )


    # -------------------------------------------------
    # Floating chatbot widget avatar (bottom-right icon).
    # -------------------------------------------------

    chatbot_avatar_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Avatar shown on the floating AI chatbot button and "
                  "its header, site-wide. Falls back to a robot icon.",
    )


    # -------------------------------------------------
    # Student Profile page hero image (left panel, like
    # the auth pages).
    # -------------------------------------------------

    profile_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Illustration shown on the Student Profile page.",
    )


    # -------------------------------------------------
    # Public Homepage content (hero section, left column)
    # -------------------------------------------------

    homepage_badge_text = models.CharField(
        max_length=100,
        default="AI Powered Placement Portal",
        blank=True,
        help_text="Small pill label above the homepage headline.",
    )

    homepage_headline = models.CharField(
        max_length=100,
        default="Smarter Careers",
        blank=True,
        help_text="First line of the homepage headline (default color).",
    )

    homepage_headline_highlight = models.CharField(
        max_length=100,
        default="Start Here",
        blank=True,
        help_text="Second line of the homepage headline, shown in the accent color.",
    )

    homepage_subtext = models.TextField(
        default=(
            "Find internships, jobs and placement opportunities with the "
            "power of AI. Get personalized job matches, resume insights "
            "and interview preparation - all in one platform."
        ),
        blank=True,
        help_text="Paragraph shown under the homepage headline.",
    )

    homepage_hero_image = models.ImageField(
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Illustration shown on the right of the homepage headline.",
    )


    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Site Branding"
        verbose_name_plural = "Site Branding"

    def save(self, *args, **kwargs):

        # Singleton - there is only ever one branding record,
        # so uploading a new logo replaces the one shown
        # everywhere instead of creating ambiguity over which
        # row is "active".
        self.pk = 1

        super().save(*args, **kwargs)

    def __str__(self):
        return self.site_name


# =====================================================
# CENTRALIZED NOTIFICATION ENGINE (Requirement 22)
# One row per event type, controlling which channels
# fire for it. Admin can toggle these without any code
# changes - jobsystem/services/notification_engine.py
# reads this table before sending anything.
# =====================================================

class NotificationChannelSetting(models.Model):

    EVENT_CHOICES = (
        ("registration_confirmation", "Registration Confirmation"),
        ("profile_verification", "Profile Verification"),
        ("new_job_alert", "New Job Alert"),
        ("application_confirmation", "Application Confirmation"),
        ("application_under_review", "Application Under Review"),
        ("shortlisted", "Shortlist Notification"),
        ("interview_scheduled", "Interview Schedule"),
        ("interview_reminder", "Interview Reminder"),
        ("selected", "Selection Notification"),
        ("rejected", "Rejection Notification"),
        ("drive_reminder", "Placement Drive Reminder"),
        ("new_job_posted_admin_alert", "New Job Posted (Admin Alert)"),
    )

    event_key = models.CharField(
        max_length=40,
        choices=EVENT_CHOICES,
        unique=True,
    )

    in_app_enabled = models.BooleanField(default=True)

    email_enabled = models.BooleanField(default=True)

    whatsapp_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["event_key"]
        verbose_name = "Notification Channel Setting"
        verbose_name_plural = "Notification Channel Settings"

    def __str__(self):
        return self.get_event_key_display()


# =====================================================
# SCHEDULED PLACEMENT REPORTS
# =====================================================


class ReportSchedule(models.Model):

    FREQUENCY_CHOICES = (
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="report_schedules"
    )

    email = models.EmailField()

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="weekly"
    )

    active = models.BooleanField(default=True)

    last_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} ({self.get_frequency_display()})"


# =====================================================
# PASSWORD RESET OTP (Student & Company accounts only)
# =====================================================


class PasswordResetOTP(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset_otps"
    )

    otp_code = models.CharField(max_length=6)

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.user.email}"


# =====================================================
# BACKGROUND JOB-MATCH ALERTS
# Tracks which (student, job) pairs have already triggered
# a background "smart match" notification, so the periodic
# scan (BackgroundJobMatchScanView) never alerts the same
# student about the same job twice.
# =====================================================


class JobMatchAlert(models.Model):

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="job_match_alerts",
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="match_alerts",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        unique_together = ("student", "job")

    def __str__(self):
        return f"{self.student} <- {self.job}"


# =====================================================
# MOCK INTERVIEW SESSIONS
# Tracks a live, in-progress (or finished) mock interview: the
# question/answer turns so far, and the final AI-generated score
# report once it concludes. chatbot.py's mock interview subsystem
# reads and writes this model directly.
# =====================================================


class MockInterviewSession(models.Model):

    STATUS_CHOICES = (
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="mock_interview_sessions",
    )

    job_title = models.CharField(
        max_length=200,
        blank=True,
    )

    turns = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {'question': str, 'answer': str|None} in order.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="in_progress",
    )

    score_report = models.JSONField(
        null=True,
        blank=True,
        help_text="Set once the session concludes: overall_score, "
                   "technical_score, communication_score, strengths, "
                   "improvements, question_feedback.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Mock interview: {self.student} - {self.job_title}"
