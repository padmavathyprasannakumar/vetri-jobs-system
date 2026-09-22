# =====================================================
# IMPORTS
# =====================================================
from django.db.migrations import serializer
from django.db.migrations import serializer
from django.shortcuts import (
    render,
    get_object_or_404
)

from django.contrib.auth import authenticate
from django.http import JsonResponse, request

from django.db import transaction

from django.contrib.auth.models import AnonymousUser

from rest_framework.views import APIView


from rest_framework.response import Response


from rest_framework import status

from django.contrib.auth import get_user_model


from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated

)

from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)



from rest_framework_simplejwt.tokens import RefreshToken

from .models import StudentResume

from .serializers import ResumeSerializer


import json

from groq import Groq

from django.conf import settings

from PyPDF2 import PdfReader


from .models import (

    User,

    StudentProfile,

    CompanyProfile,

    CompanyRegistrationPhoto,

    PlacementAdminProfile,

    ResumeAnalysis,

)



from .serializers import (

    UserSerializer,

    RegisterSerializer

)

from .utils.resume_parser import extract_resume_text

from .services.resume_ai import analyse_resume_with_ai

from .services.job_matching import compute_job_match

def analyze_resume_with_groq(text):


    client = Groq(

        api_key=settings.GROQ_API_KEY

    )


    prompt=f"""

You are an AI resume analyser.

Analyse this resume:

{text}


Return ONLY JSON:

{{

"score": number,

"skills": [],

"experience":"",

"education":"",

"certifications":[],

"projects":[],

"missing_information":[],

"job_categories":[]

}}

"""


    response = client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        messages=[

            {
                "role":"user",
                "content":prompt
            }

        ],

        temperature=0.2

    )


    result=response.choices[0].message.content


    return json.loads(result)







# =====================================================
# JWT TOKEN GENERATOR
# =====================================================


def generate_tokens(user):


    refresh = RefreshToken.for_user(user)



    return {


        "refresh":

            str(refresh),



        "access":

            str(refresh.access_token)


    }









# =====================================================
# REGISTER USER
# =====================================================


class RegisterView(APIView):


    permission_classes = [

        AllowAny

    ]





    def post(self,request):



        serializer = RegisterSerializer(

            data=request.data

        )




        if not serializer.is_valid():


            return Response(

                {

                    "success":False,


                    "errors":

                    serializer.errors

                },


                status=status.HTTP_400_BAD_REQUEST

            )





        try:



            with transaction.atomic():



                user = serializer.save()






                # ===============================
                # CREATE PROFILE AUTOMATICALLY
                # ===============================



                if user.role == "student":



                    StudentProfile.objects.get_or_create(


                        user=user,


                        defaults={


                            "full_name":

                            user.username,

                            # student_id has unique=True but isn't
                            # collected on this form - if left at
                            # the CharField's implicit "" default,
                            # the *second* student to register with
                            # no ID would collide on that empty
                            # string and registration would fail
                            # with a generic "unique constraint"
                            # error. Explicit None avoids that,
                            # since unique=True doesn't apply
                            # across multiple NULLs.
                            "student_id":

                            None


                        }


                    )


                    # ===============================
                    # WELCOME NOTIFICATION + WHATSAPP
                    # (routed through the centralized engine so
                    # admin channel toggles apply here too)
                    # ===============================

                    try:

                        from jobsystem.services.notification_engine import dispatch

                        dispatch(
                            "registration_confirmation",
                            user,
                            {"name": user.username},
                        )

                    except Exception as e:

                        print("RegisterView welcome notification error:", e)






                elif user.role == "company":



                    CompanyProfile.objects.get_or_create(


                        user=user,


                        defaults={


                            "company_name":

                            user.username


                        }


                    )






                elif user.role == "placement_admin":



                    PlacementAdminProfile.objects.get_or_create(


                        user=user,


                        defaults={


                            "full_name":

                            user.username


                        }


                    )







                tokens = generate_tokens(user)








                return Response(

                    {



                        "success":True,



                        "message":

                        "Registration successful",





                        "user":

                        UserSerializer(user).data,





                        "access":

                        tokens["access"],





                        "refresh":

                        tokens["refresh"]



                    },


                    status=status.HTTP_201_CREATED


                )






        except Exception as e:



            print("RegisterView error:", e)


            error_text = str(e).lower()

            if "unique" in error_text and "username" in error_text:

                friendly_message = "This username is already taken."

            elif "unique" in error_text and "email" in error_text:

                friendly_message = "An account with this email already exists."

            elif "unique" in error_text and "student_id" in error_text:

                friendly_message = (
                    "A student profile setup issue occurred. "
                    "Please try registering again."
                )

            elif "unique" in error_text:

                friendly_message = "An account with these details already exists."

            else:

                friendly_message = "Registration failed. Please try again."


            return Response(


                {


                    "success":False,


                    "message":

                    friendly_message,



                    "error":

                    str(e)



                },


                status=status.HTTP_500_INTERNAL_SERVER_ERROR


            )









# =====================================================
# COMPANY REGISTRATION (with document upload + admin approval)
# =====================================================


class CompanyRegisterView(APIView):

    """
    Dedicated company registration endpoint. Unlike the generic
    RegisterView, this:
      - accepts multipart/form-data (company details + uploaded
        documents/photos)
      - never issues login tokens - the account starts with
        approval_status="pending" and can only log in once a
        placement admin approves it (see LoginView's company
        gate, and the placement Companies approve/reject views).
    """

    permission_classes = [AllowAny]

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):

        data = request.data

        required_fields = [
            "company_name", "username", "email",
            "password", "confirm_password",
        ]

        for field in required_fields:

            if not (data.get(field) or "").strip():

                return Response(
                    {"error": f"{field.replace('_',' ').title()} is required."},
                    status=400
                )

        if data.get("password") != data.get("confirm_password"):

            return Response(
                {"error": "Password and confirm password do not match."},
                status=400
            )

        if not request.FILES.get("registration_document"):

            return Response(
                {"error": "Company registration document is required."},
                status=400
            )

        if not request.FILES.get("gst_document"):

            return Response(
                {"error": "GST document is required."},
                status=400
            )

        username = data.get("username").strip()

        email = data.get("email").strip()

        if User.objects.filter(username__iexact=username).exists():

            return Response(
                {"error": "This username is already taken."},
                status=400
            )

        if User.objects.filter(email__iexact=email).exists():

            return Response(
                {"error": "An account with this email already exists."},
                status=400
            )

        try:

            with transaction.atomic():

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=data.get("password"),
                    role="company",
                    phone=data.get("phone", ""),
                )

                company = CompanyProfile.objects.create(
                    user=user,
                    company_name=data.get("company_name").strip(),
                    address=data.get("address", ""),
                    website=data.get("website", ""),
                    linkedin=data.get("linkedin", ""),
                    instagram=data.get("instagram", ""),
                    facebook=data.get("facebook", ""),
                    registration_document=request.FILES.get("registration_document"),
                    gst_document=request.FILES.get("gst_document"),
                    approval_status="pending",
                )

                photos = request.FILES.getlist("company_photos")

                for photo in photos[:5]:

                    CompanyRegistrationPhoto.objects.create(
                        company=company,
                        photo=photo,
                    )

            return Response(
                {
                    "success": True,
                    "message": (
                        "Your application has been submitted for review. "
                        "You'll be able to log in once an admin approves it."
                    ),
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:

            return Response(
                {
                    "success": False,
                    "message": "Registration failed",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CompanyRegistrationStatusView(APIView):

    """
    Lets a company check their registration approval status using
    their login credentials, without actually logging them in (the
    whole point is that login is blocked while pending/rejected).
    """

    permission_classes = [AllowAny]

    def post(self, request):

        identifier = (request.data.get("username") or "").strip()

        password = request.data.get("password")

        if not identifier or not password:

            return Response(
                {"error": "Username and password are required."},
                status=400
            )

        user = User.objects.filter(

            username__iexact=identifier

        ).first() or User.objects.filter(

            email__iexact=identifier

        ).first()

        if not user or not user.check_password(password):

            return Response(
                {"error": "Invalid username or password."},
                status=401
            )

        if user.role != "company":

            return Response(
                {"error": "Invalid username or password."},
                status=401
            )

        company = CompanyProfile.objects.filter(user=user).first()

        if not company:

            return Response(
                {"error": "No company application found for this account."},
                status=404
            )

        return Response(
            {
                "company_name": company.company_name,
                "approval_status": company.approval_status,
                "rejection_reason": company.rejection_reason,
                "submitted_on": company.created_at,
            }
        )



# =====================================================
# LOGIN USER
# =====================================================


class ForgotPasswordView(APIView):

    """
    POST /auth/forgot-password/  { "email": "..." }

    Sends a 6-digit OTP by email. Restricted to student and
    company accounts only - placement_admin and super_admin
    should use their own admin-managed credential recovery,
    not a self-service OTP.

    Always returns the same generic message whether or not the
    email exists / is eligible, so this can't be used to probe
    which emails are registered.
    """

    permission_classes = [AllowAny]

    def post(self, request):

        email = (request.data.get("email") or "").strip()

        if not email:

            return Response(
                {"error": "Email is required"},
                status=400
            )

        generic_response = Response(
            {
                "message":
                "If an eligible account exists for that email, a "
                "6-digit verification code has been sent."
            }
        )

        user = User.objects.filter(email__iexact=email).first()

        if not user or user.role not in ("student", "company"):

            return generic_response

        try:

            import random

            from django.utils import timezone

            from datetime import timedelta

            from django.conf import settings as dj_settings

            from django.core.mail import send_mail

            from .models import PasswordResetOTP

            otp_code = f"{random.randint(0, 999999):06d}"

            PasswordResetOTP.objects.create(
                user=user,
                otp_code=otp_code,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

            send_mail(
                subject="Vetri Jobs - Your password reset code",
                message=(
                    f"Hi {user.username},\n\n"
                    "Your Vetri Jobs password reset code is:\n\n"
                    f"    {otp_code}\n\n"
                    "This code expires in 10 minutes and can only "
                    "be used once. If you didn't request this, you "
                    "can safely ignore this email."
                ),
                from_email=getattr(dj_settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=False,
            )

        except Exception as e:

            print("ForgotPasswordView error:", e)

        return generic_response


class ResetPasswordConfirmView(APIView):

    """
    POST /auth/reset-password-confirm/
    { "email": "...", "otp": "...", "new_password": "...",
      "confirm_password": "..." }
    """

    permission_classes = [AllowAny]

    def post(self, request):

        email = (request.data.get("email") or "").strip()

        otp = (request.data.get("otp") or "").strip()

        new_password = request.data.get("new_password")

        confirm_password = request.data.get("confirm_password")

        if not all([email, otp, new_password, confirm_password]):

            return Response(
                {"error": "All fields are required"},
                status=400
            )

        if new_password != confirm_password:

            return Response(
                {"error": "Passwords do not match"},
                status=400
            )

        if len(new_password) < 8:

            return Response(
                {"error": "Password must be at least 8 characters"},
                status=400
            )

        user = User.objects.filter(
            email__iexact=email,
            role__in=("student", "company"),
        ).first()

        if not user:

            return Response(
                {"error": "Invalid verification code."},
                status=400
            )

        from django.utils import timezone

        from .models import PasswordResetOTP

        record = PasswordResetOTP.objects.filter(
            user=user,
            otp_code=otp,
            is_used=False,
        ).order_by("-created_at").first()

        if not record or record.expires_at < timezone.now():

            return Response(
                {"error": "This code is invalid or has expired."},
                status=400
            )

        user.set_password(new_password)

        user.save()

        record.is_used = True

        record.save()

        return Response(
            {"message": "Your password has been reset successfully."}
        )


class LoginView(APIView):


    permission_classes=[

        AllowAny

    ]





    def post(self,request):



        email = request.data.get(

            "email"

        )



        password = request.data.get(

            "password"

        )






        try:



            user_obj = User.objects.get(

                email__iexact=(email or "").strip()

            )



        except User.DoesNotExist:



            return Response(


                {


                    "message":

                    "Invalid email or password"


                },


                status=status.HTTP_401_UNAUTHORIZED


            )







        user = authenticate(


            username=email,


            password=password


        )






        if not user:



            return Response(


                {


                    "message":

                    "Invalid email or password"


                },


                status=status.HTTP_401_UNAUTHORIZED


            )







        if not user.is_active:



            return Response(


                {


                    "message":

                    "Account disabled"


                },


                status=status.HTTP_403_FORBIDDEN


            )


        if user.role == "company":

            company_profile = CompanyProfile.objects.filter(user=user).first()

            if company_profile and company_profile.approval_status != "approved":

                if company_profile.approval_status == "rejected":

                    message = (
                        "Your company registration was rejected. "
                        + (company_profile.rejection_reason or
                           "Please contact the placement team for details.")
                    )

                else:

                    message = (
                        "Your company registration is still under review. "
                        "You'll be able to log in once an admin approves it."
                    )

                return Response(

                    {

                        "message": message,

                        "approval_status": company_profile.approval_status,

                    },

                    status=status.HTTP_403_FORBIDDEN

                )


        tokens = generate_tokens(user)







        return Response(

            {


                "success":True,



                "message":

                "Login successful",




                "user":

                UserSerializer(user).data,




                "access":

                tokens["access"],




                "refresh":

                tokens["refresh"]



            },


            status=status.HTTP_200_OK


        )









# =====================================================
# CURRENT USER
# =====================================================


class CurrentUserView(APIView):


    permission_classes=[

        IsAuthenticated

    ]





    def get(self,request):



        return Response(



            UserSerializer(

                request.user

            ).data



        )









# =====================================================
# UPDATE PROFILE
# =====================================================


class UpdateProfileView(APIView):


    permission_classes=[

        IsAuthenticated

    ]





    def put(self,request):


        user=request.user





        serializer = UserSerializer(


            user,


            data=request.data,


            partial=True


        )






        if serializer.is_valid():



            serializer.save()



            return Response(


                {


                    "success":True,



                    "message":

                    "Profile updated",



                    "user":

                    serializer.data


                }


            )






        return Response(


            serializer.errors,


            status=status.HTTP_400_BAD_REQUEST


        )









# =====================================================
# LOGOUT
# =====================================================


class LogoutView(APIView):


    permission_classes=[

        IsAuthenticated

    ]





    def post(self,request):



        try:



            refresh = request.data.get(

                "refresh"

            )




            if refresh:



                token = RefreshToken(

                    refresh

                )



                token.blacklist()





            return Response(

                {


                    "success":True,



                    "message":

                    "Logout successful"


                }

            )




        except Exception as e:



            return Response(

                {


                    "success":False,


                    "error":

                    str(e)


                },


                status=status.HTTP_400_BAD_REQUEST


            )


        from django.shortcuts import get_object_or_404


from .models import (

    Education,

    Skill,

    Resume,

    Experience,

    Job,

    Application,

    Interview,

    Notification,

    SavedJob

)


from .serializers import (

    StudentProfileSerializer,

    StudentProfileUpdateSerializer,

    EducationSerializer,

    SkillSerializer,

    ResumeSerializer,

    ExperienceSerializer,

    JobSerializer,

    ApplicationSerializer,

    ApplicationCreateSerializer,

    InterviewSerializer,

    NotificationSerializer

)

# =====================================================
# STUDENT PROFILE
# =====================================================


class StudentProfileView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if request.user.role != "student":


            return Response(

                {
                    "error":
                    "Student access only"
                },

                status=403

            )



        profile = request.user.student_profile



        serializer = StudentProfileSerializer(

            profile

        )


        return Response(

            serializer.data

        )





    def put(self,request):


        profile = request.user.student_profile



        serializer = StudentProfileUpdateSerializer(

            profile,

            data=request.data,

            partial=True

        )



        if serializer.is_valid():

            serializer.save()



            return Response(

                {
                    "message":
                    "Profile updated",

                    "data":
                    serializer.data
                }

            )


        return Response(

            serializer.errors,

            status=400

        )


    # =====================================================
# EDUCATION
# =====================================================


class EducationListCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        education = Education.objects.filter(

            student=request.user.student_profile

        )


        serializer = EducationSerializer(

            education,

            many=True

        )


        return Response(

            serializer.data

        )





    def post(self,request):


        serializer = EducationSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save(

                student=request.user.student_profile

            )


            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )


    # =====================================================
# SKILLS
# =====================================================


class SkillCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        skills = Skill.objects.filter(

            student=request.user.student_profile

        )


        serializer = SkillSerializer(

            skills,

            many=True

        )


        return Response(

            serializer.data

        )





    def post(self,request):


        serializer = SkillSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save(

                student=request.user.student_profile

            )



            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )


# =====================================================
# STUDENT RESUME UPLOAD + AI ANALYSIS
# =====================================================

class ResumeUploadView(APIView):

    permission_classes=[
        IsAuthenticated
    ]



    def get(self,request):

        resumes = Resume.objects.filter(

            student=request.user.student_profile

        ).order_by("-uploaded_at")


        serializer=ResumeSerializer(

            resumes,

            many=True

        )


        return Response(
            serializer.data
        )




    def post(self,request):


        serializer=ResumeSerializer(

            data=request.data

        )


        if serializer.is_valid():


            resume=serializer.save(

                student=request.user.student_profile

            )


            try:


                text=extract_resume_text(

                    resume.file

                )


                analysis=analyse_resume_with_ai(

                    text

                )



                ResumeAnalysis.objects.create(

                    resume=resume,

                    skills=analysis.get(
                        "skills",
                        []
                    ),

                    experience=analysis.get(
                        "experience",
                        []
                    ),


                    education=analysis.get(
                        "education",
                        []
                    ),


                    certifications=analysis.get(
                        "certifications",
                        []
                    ),


                    projects=analysis.get(
                        "projects",
                        []
                    ),


                    missing_information=analysis.get(
                        "missing_information",
                        []
                    ),


                    job_categories=analysis.get(
                        "job_categories",
                        []
                    ),


                    resume_score=analysis.get(
                        "resume_score",
                        0
                    )

                )



            except Exception as e:


                print(
                    "AI ERROR:",
                    e
                )


                analysis={
                    "error":str(e)
                }



            return Response({

                "message":
                "Resume uploaded and analysed",


                "resume":
                serializer.data,


                "analysis":
                analysis

            },status=201)



        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# STUDENT JOB LIST
# =====================================================


class StudentJobListView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def get(self,request):


        jobs = Job.objects.filter(
            status="active",
            is_active=True
        ).order_by("-created_at")


        data=[]


        try:

            saved_job_ids = set(
                SavedJob.objects.filter(
                    student=request.user.student_profile
                ).values_list("job_id", flat=True)
            )

        except Exception as e:

            # Table not migrated yet, or any other lookup issue -
            # never let this take down the whole job list.

            print("SavedJob lookup failed (run migrations?):", e)

            saved_job_ids = set()


        for job in jobs:


            try:

                serializer = JobSerializer(job).data


                serializer["is_applied"] = Application.objects.filter(
                    student=request.user.student_profile,
                    job=job
                ).exists()


                serializer["is_saved"] = job.id in saved_job_ids


                match_score, match_reasons = compute_job_match(
                    request.user.student_profile,
                    job
                )

                serializer["match_score"] = match_score

                serializer["match_reasons"] = match_reasons


                data.append(serializer)

            except Exception as e:

                # Never let one bad job record blank out the whole list.

                print("Error serializing job", job.id, ":", e)

                continue


        return Response(data)


    # =====================================================
    # SAVE / UNSAVE A JOB
    # POST   /student/jobs/<id>/save/   -> bookmark it
    # DELETE /student/jobs/<id>/save/   -> remove bookmark
    # =====================================================


class SaveJobView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def post(self, request, job_id):

        job = get_object_or_404(
            Job,
            id=job_id
        )

        profile = getattr(request.user, "student_profile", None)

        if not profile:

            return Response(
                {
                    "error":
                    "Please complete your student profile before "
                    "saving jobs."
                },
                status=400
            )

        try:

            saved, created = SavedJob.objects.get_or_create(
                student=profile,
                job=job,
            )

        except Exception as e:

            print("SaveJobView error:", e)

            return Response(
                {
                    "error":
                    "Unable to save this job right now. If this "
                    "keeps happening, the server may need its "
                    "database migrations run."
                },
                status=500
            )

        return Response(
            {
                "message":
                "Job saved" if created else "Job already saved"
            },
            status=201 if created else 200
        )

    def delete(self, request, job_id):

        deleted, _ = SavedJob.objects.filter(
            student=request.user.student_profile,
            job_id=job_id,
        ).delete()

        return Response(
            {
                "message":
                "Job removed from saved list"
                if deleted
                else "Job was not saved"
            }
        )


    # =====================================================
    # LIST SAVED JOBS
    # GET /student/saved-jobs/
    # Returns flat Job objects (same shape as the main job
    # list) so the Saved Jobs page can reuse the same card
    # fields (title/company/location/salary/job_type/id).
    # =====================================================


class StudentSavedJobsView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self, request):

        profile = getattr(request.user, "student_profile", None)

        if not profile:

            return Response(
                {
                    "error":
                    "Please complete your student profile first."
                },
                status=400
            )

        try:

            jobs = Job.objects.filter(
                saved_by__student=profile
            ).order_by(
                "-saved_by__saved_at"
            )

            data = JobSerializer(
                jobs,
                many=True
            ).data

        except Exception as e:

            print("StudentSavedJobsView error:", e)

            return Response(
                {
                    "error":
                    "Unable to load saved jobs right now."
                },
                status=500
            )

        return Response(data)


    # =====================================================
    # SINGLE JOB DETAILS
    # GET /student/jobs/<id>/
    # Includes is_applied/is_saved, AI match score + reasons,
    # and a short "similar jobs" list.
    # =====================================================


class StudentJobDetailView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self, request, job_id):

        job = get_object_or_404(
            Job,
            id=job_id
        )

        profile = getattr(request.user, "student_profile", None)

        if not profile:

            return Response(
                {
                    "error":
                    "Please complete your student profile first."
                },
                status=400
            )

        data = JobSerializer(job).data

        data["is_applied"] = Application.objects.filter(
            student=profile,
            job=job
        ).exists()

        try:

            data["is_saved"] = SavedJob.objects.filter(
                student=profile,
                job=job
            ).exists()

        except Exception as e:

            # Never let a missing/un-migrated SavedJob table take
            # down the whole job details page - this was the
            # actual cause of "View Details" always failing.

            print("StudentJobDetailView SavedJob lookup error:", e)

            data["is_saved"] = False

        try:

            match_score, match_reasons = compute_job_match(
                profile,
                job
            )

        except Exception as e:

            print("StudentJobDetailView match score error:", e)

            match_score, match_reasons = 0, []

        data["match_score"] = match_score

        data["match_reasons"] = match_reasons


        try:

            similar_qs = Job.objects.filter(
                status="active",
                is_active=True,
                job_type=job.job_type
            ).exclude(
                id=job.id
            ).order_by("-created_at")[:4]

            data["similar_jobs"] = [
                {
                    "id": s.id,
                    "title": s.title,
                    "company": (
                        s.company.company_name
                        if s.company else ""
                    ),
                    "location": s.location,
                }
                for s in similar_qs
            ]

        except Exception as e:

            print("StudentJobDetailView similar_jobs error:", e)

            data["similar_jobs"] = []


        return Response(data)

    # =====================================================
    # APPLY JOB
    # =====================================================


class ApplyJobView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request,job_id):


        if request.user.role != "student":


            return Response(

                {
                    "error":
                    "Student only"
                },

                status=403

            )



        job = get_object_or_404(

            Job,

            id=job_id

        )



        resume_id=request.data.get(

            "resume"

        )



        resume=None



        if resume_id:


            resume=get_object_or_404(

                Resume,

                id=resume_id,

                student=request.user

            )





        application,created = Application.objects.get_or_create(

            student=request.user.student_profile,

            job=job,

            defaults={

                "resume":resume,

                "cover_letter":

                request.data.get(

                    "cover_letter",

                    ""

                )

            }

        )





        if not created:


            return Response(

                {
                    "message":
                    "Already applied"
                },

                status=400

            )







        try:

            from jobsystem.services.notification_engine import dispatch

            dispatch(
                "application_confirmation",
                request.user,
                {
                    "job_title": job.title,
                    "company_name": (
                        job.company.company_name
                        if job.company else "the company"
                    ),
                },
            )

        except Exception as e:

            print("Notification dispatch error:", e)


        return Response(

            {
                "message":
                "Application submitted"

            },

            status=201

        )

    # =====================================================
# MY APPLICATIONS
# =====================================================


class StudentApplicationsView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        applications = Application.objects.filter(

            student=request.user.student_profile

        )



        serializer = ApplicationSerializer(

            applications,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# STUDENT INTERVIEWS
# =====================================================


class StudentInterviewView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        interviews = Interview.objects.filter(

            application__student=request.user.student_profile

        )



        serializer = InterviewSerializer(

            interviews,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# STUDENT NOTIFICATIONS
# =====================================================


class StudentNotificationView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        notifications = Notification.objects.filter(

            user=request.user

        )



        serializer = NotificationSerializer(

            notifications,

            many=True

        )


        return Response(

            serializer.data

        )

    from datetime import datetime


from .models import (

    CompanyProfile,

    Job,

    Application,

    CandidateReview,

    Interview

)


from .serializers import (

    CompanyProfileSerializer,

    CompanyProfileUpdateSerializer,

    JobSerializer,

    JobCreateSerializer,

    ApplicationSerializer,

    CandidateReviewSerializer,

    CandidateShortlistSerializer,

    InterviewSerializer,

    InterviewCreateSerializer,

    ApplicationStatusSerializer

)


# =====================================================
# COMPANY DASHBOARD
# =====================================================


class CompanyDashboardView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count

        company = getattr(
            request.user, "company_profile", None
        )

        if not company:

            return Response(
                {
                    "error":
                    "Company profile not found. Please "
                    "complete your company profile first."
                },
                status=404
            )

        jobs_qs = Job.objects.filter(
            company=company
        )

        applications_qs = Application.objects.filter(
            job__company=company
        )

        active_jobs = jobs_qs.filter(
            status="active"
        ).count()

        total_applications = applications_qs.count()

        total_candidates = applications_qs.values(
            "student_id"
        ).distinct().count()

        interviews_scheduled = Interview.objects.filter(
            application__job__company=company,
            status="scheduled"
        ).count()


        # -------------------------------------------------
        # Applications overview - last 30 days, one point
        # per day, so the frontend can draw a simple line
        # chart without doing any date math itself.
        # -------------------------------------------------

        today = timezone.now().date()

        overview = []

        for i in range(29, -1, -1):

            day = today - timedelta(days=i)

            count = applications_qs.filter(
                applied_date__date=day
            ).count()

            overview.append({
                "date": day.strftime("%b %d"),
                "count": count,
            })


        # -------------------------------------------------
        # Applications by status (donut chart)
        # -------------------------------------------------

        status_counts = (
            applications_qs
            .values("status")
            .annotate(total=Count("id"))
        )

        status_map = {
            row["status"]: row["total"]
            for row in status_counts
        }

        by_status = [
            {
                "status": "Applied",
                "count": status_map.get("applied", 0),
            },
            {
                "status": "Shortlisted",
                "count": status_map.get("shortlisted", 0),
            },
            {
                "status": "Interview",
                "count": status_map.get("interview", 0),
            },
            {
                "status": "Hired",
                "count": status_map.get("selected", 0),
            },
            {
                "status": "Rejected",
                "count": status_map.get("rejected", 0),
            },
        ]


        # -------------------------------------------------
        # Recent job postings (with live application counts)
        # -------------------------------------------------

        recent_jobs = []

        for job in jobs_qs.order_by("-created_at")[:6]:

            recent_jobs.append({
                "id": job.id,
                "title": job.title,
                "applications": job.applications.count(),
                "status": job.get_status_display(),
                "posted_on": job.created_at,
            })


        # -------------------------------------------------
        # Recent applications (candidates)
        # -------------------------------------------------

        recent_applications = []

        for app in applications_qs.select_related(
            "student", "job"
        ).order_by("-applied_date")[:6]:

            recent_applications.append({
                "id": app.id,
                "name": app.student.full_name,
                "job_title": app.job.title,
                "status": app.get_status_display(),
                "applied_date": app.applied_date,
            })


        profile_completion = getattr(
            company, "profile_completion", 0
        )


        # -------------------------------------------------
        # AI Recommended Candidates - top applicants by
        # match score across this company's recent jobs.
        # -------------------------------------------------

        top_candidates = []

        try:

            for app in applications_qs.select_related(
                "student", "job"
            ).exclude(
                status__in=["rejected", "withdrawn"]
            ).order_by("-applied_date")[:15]:

                score, _ = compute_job_match(app.student, app.job)

                top_candidates.append({
                    "application_id": app.id,
                    "student_id": app.student.id,
                    "name": app.student.full_name,
                    "job_title": app.job.title,
                    "match_score": score,
                    "skills": (
                        app.student.skills.split(",")[:4]
                        if app.student.skills else []
                    ),
                })

            top_candidates.sort(
                key=lambda c: c["match_score"], reverse=True
            )

            top_candidates = top_candidates[:4]

        except Exception as e:

            print("CompanyDashboardView top_candidates error:", e)

            top_candidates = []


        return Response({

            "profile_completion": profile_completion,

            "stats": {
                "active_jobs": active_jobs,
                "total_applications": total_applications,
                "total_candidates": total_candidates,
                "interviews_scheduled": interviews_scheduled,
            },

            "applications_overview": overview,

            "applications_by_status": by_status,

            "recent_jobs": recent_jobs,

            "recent_applicants": recent_applications,

            "top_candidates": top_candidates,

            # kept for backwards compatibility with the
            # older/simpler dashboard fields, in case anything
            # else still reads these flat keys directly
            "total_jobs": active_jobs,
            "total_applicants": total_applications,
            "shortlisted": status_map.get("shortlisted", 0),
            "upcoming_interviews": interviews_scheduled,

        })


# =====================================================
# COMPANY ANALYTICS
# =====================================================


class CompanyAnalyticsView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count

        company = getattr(
            request.user, "company_profile", None
        )

        if not company:

            return Response(
                {
                    "error":
                    "Company profile not found."
                },
                status=404
            )

        jobs_qs = Job.objects.filter(company=company)

        applications_qs = Application.objects.filter(
            job__company=company
        )

        interviews_qs = Interview.objects.filter(
            application__job__company=company
        )


        stats = {

            "total_jobs_posted": jobs_qs.count(),

            "total_applications": applications_qs.count(),

            "interviews_scheduled": interviews_qs.count(),

            "hired_candidates": applications_qs.filter(
                status="selected"
            ).count(),

        }


        # -------------------------------------------------
        # Job Posting & Applications Trend - last 7 days
        # -------------------------------------------------

        today = timezone.now().date()

        trend = []

        for i in range(6, -1, -1):

            day = today - timedelta(days=i)

            trend.append({

                "date": day.strftime("%b %d"),

                "applications": applications_qs.filter(
                    applied_date__date=day
                ).count(),

                "job_postings": jobs_qs.filter(
                    created_at__date=day
                ).count(),

            })


        # -------------------------------------------------
        # Applications by Job Type
        # -------------------------------------------------

        type_counts = (
            applications_qs
            .values("job__job_type")
            .annotate(total=Count("id"))
        )

        type_map = {
            row["job__job_type"]: row["total"]
            for row in type_counts
        }

        total_type_count = sum(type_map.values()) or 1

        job_type_labels = dict(Job.JOB_TYPE_CHOICES)

        by_job_type = []

        for code, label in job_type_labels.items():

            count = type_map.get(code, 0)

            if count == 0:

                continue

            by_job_type.append({

                "label": label,

                "count": count,

                "percent": round((count / total_type_count) * 100),

            })


        # -------------------------------------------------
        # Top Departments
        # -------------------------------------------------

        dept_counts = (
            jobs_qs
            .exclude(department="")
            .values("department")
            .annotate(total=Count("id"))
            .order_by("-total")[:5]
        )

        top_departments = [
            {
                "department": row["department"],
                "count": row["total"],
            }
            for row in dept_counts
        ]


        # -------------------------------------------------
        # Recent Activity feed
        # -------------------------------------------------

        activity = []

        for app in applications_qs.select_related(
            "job"
        ).order_by("-applied_date")[:3]:

            activity.append({
                "message": f"New application received for {app.job.title}",
                "timestamp": app.applied_date,
                "type": "application",
            })

        for iv in interviews_qs.select_related(
            "application", "application__student"
        ).order_by("-created_at")[:3]:

            activity.append({
                "message": f"Interview scheduled with {iv.application.student.full_name}",
                "timestamp": iv.created_at,
                "type": "interview",
            })

        for job in jobs_qs.order_by("-created_at")[:3]:

            activity.append({
                "message": f"Job posted: {job.title}",
                "timestamp": job.created_at,
                "type": "job",
            })

        for app in applications_qs.filter(
            status="shortlisted"
        ).select_related("student").order_by("-updated_at")[:3]:

            activity.append({
                "message": f"Candidate shortlisted: {app.student.full_name}",
                "timestamp": app.updated_at,
                "type": "shortlist",
            })

        activity.sort(
            key=lambda a: a["timestamp"],
            reverse=True
        )

        activity = activity[:8]


        return Response({

            "stats": stats,

            "trend": trend,

            "applications_by_job_type": by_job_type,

            "top_departments": top_departments,

            "recent_activity": activity,

        })


# =====================================================
# COMPANY PROFILE
# =====================================================


class CompanyProfileView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if request.user.role != "company":


            return Response(

                {
                    "error":
                    "Company access only"
                },

                status=403

            )


        profile = request.user.company_profile



        serializer = CompanyProfileSerializer(

            profile,
            context={"request": request}

        )


        return Response(

            serializer.data

        )





    def put(self,request):


        profile = request.user.company_profile



        serializer = CompanyProfileUpdateSerializer(

            profile,

            data=request.data,

            partial=True

        )



        if serializer.is_valid():


            serializer.save()



            return Response(

                {

                    "message":
                    "Company profile updated",

                    "data":
                    CompanyProfileSerializer(
                        profile,
                        context={"request": request}
                    ).data

                }

            )



        return Response(

            serializer.errors,

            status=400

        )


    # =====================================================
    # UPLOAD COMPANY LOGO
    # POST /company/profile/logo/
    # =====================================================


class CompanyLogoUploadView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def post(self, request):

        if request.user.role != "company":

            return Response(
                {
                    "error":
                    "Company access only"
                },
                status=403
            )

        profile = request.user.company_profile

        logo = request.FILES.get("logo")

        if not logo:

            return Response(
                {
                    "error":
                    "No logo file provided"
                },
                status=400
            )

        profile.logo = logo

        profile.save()

        serializer = CompanyProfileSerializer(
            profile,
            context={"request": request}
        )

        return Response(
            {
                "message":
                "Logo updated",
                "data":
                serializer.data
            }
        )


    # =====================================================
    # CREATE JOB
    # =====================================================


class CompanyCreateJobView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def post(self,request):


        user_role = request.user.role

        target_company = None

        if user_role == "company":

            target_company = request.user.company_profile

        elif user_role in ("placement_admin", "super_admin"):

            company_id = request.data.get("company_id") or request.data.get("company")

            if not company_id:

                return Response(
                    {
                        "error":
                        "Please select which company this job is for."
                    },
                    status=400
                )

            target_company = CompanyProfile.objects.filter(
                id=company_id
            ).first()

            if not target_company:

                return Response(
                    {
                        "error":
                        "Company not found."
                    },
                    status=404
                )

        else:

            return Response(
                {
                    "error":
                    "You don't have permission to create jobs."
                },
                status=403
            )


        serializer = JobCreateSerializer(
            data=request.data
        )


        if serializer.is_valid():

            job = serializer.save(

    company=target_company

            )


            # Respect the "Is this job active?" toggle from the
            # Post Job form instead of always forcing it active.

            requested_status = request.data.get("status")

            if requested_status in dict(Job.STATUS_CHOICES):

                job.status = requested_status

                job.is_active = requested_status == "active"

            else:

                job.status = "active"

                job.is_active = True

            job.save()

            try:

                from jobsystem.services.notification_engine import (
                    notify_placement_admins
                )

                notify_placement_admins(
                    "new_job_posted_admin_alert",
                    {
                        "job_title": job.title,
                        "company_name": target_company.company_name,
                        "location": job.location,
                    },
                )

            except Exception as e:

                print("CompanyCreateJobView notify error:", e)

            return Response(

                {
                    "message":
                    "Job created successfully",

                    "data":
                    JobSerializer(job).data
                },

                status=201
            )


        return Response(

            serializer.errors,

            status=400
        )
   # =====================================================
# COMPANY JOB LIST
# =====================================================


class CompanyJobListView(APIView):


    permission_classes=[
        IsAuthenticated
    ]



    def get(self,request):


        if request.user.role != "company":

            return Response(
                {
                    "error":
                    "Company only"
                },
                status=403
            )



        jobs = Job.objects.filter(
            company=request.user.company_profile
        ).order_by(
            "-created_at"
        )



        serializer = JobSerializer(
            jobs,
            many=True
        )



        return Response(
            serializer.data,
            status=200
        )


    # =====================================================
# UPDATE JOB
# =====================================================


class CompanyJobUpdateView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def put(self,request,job_id):


        job = Job.objects.get(
            id=job_id,
            company=request.user.company_profile
        )


        serializer = JobSerializer(
            job,
            data=request.data,
            partial=True
        )


        if serializer.is_valid():

            serializer.save()


            return Response({

                "message":
                "Job updated successfully",

                "data":
                serializer.data

            })


        return Response(
            serializer.errors,
            status=400
        )

    # =====================================================
# DELETE JOB
# =====================================================


class CompanyJobDeleteView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def delete(self,request,job_id):


        job = get_object_or_404(

            Job,

            id=job_id,

            company=request.user.company_profile

        )



        job.delete()



        return Response(

            {

                "message":
                "Job deleted"

            }

        )

    # =====================================================
# COMPANY CANDIDATES
# =====================================================


# =====================================================
# AI CANDIDATE SEARCH - proactive sourcing across the
# whole student database (not just people who applied),
# so recruiters can search by skill/department/location.
# =====================================================

class CompanyCandidateSearchView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        from django.db.models import Q

        company = getattr(request.user, "company_profile", None)

        if not company:

            return Response(
                {"error": "Company profile not found."},
                status=404
            )

        query = request.query_params.get("q", "").strip()

        department = request.query_params.get("department", "").strip()

        min_cgpa = request.query_params.get("min_cgpa", "").strip()

        candidates_qs = StudentProfile.objects.select_related("user")

        if query:

            candidates_qs = candidates_qs.filter(
                Q(skills__icontains=query) |
                Q(full_name__icontains=query) |
                Q(course__icontains=query) |
                Q(department__icontains=query)
            )

        if department:

            candidates_qs = candidates_qs.filter(
                department__icontains=department
            )

        if min_cgpa:

            try:

                candidates_qs = candidates_qs.filter(
                    ug_cgpa__gte=float(min_cgpa)
                )

            except ValueError:

                pass

        candidates_qs = candidates_qs.order_by("-id")[:30]

        results = []

        for student in candidates_qs:

            results.append({
                "student_id": student.id,
                "name": student.full_name,
                "course": student.course,
                "department": student.department,
                "graduation_year": student.graduation_year,
                "cgpa": student.ug_cgpa,
                "location": student.location,
                "skills": (
                    [s.strip() for s in student.skills.split(",")]
                    if student.skills else []
                ),
            })

        return Response({
            "count": len(results),
            "results": results,
        })


class CompanyCandidatesView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        from django.utils import timezone
        from datetime import timedelta
        from jobsystem.services.job_matching import compute_job_match


        company = request.user.company_profile


        applications = Application.objects.filter(

            job__company=company

        ).select_related(

            "student", "student__user", "job", "resume"

        ).order_by("-applied_date")


        candidates = []

        for app in applications:

            try:


                match_score, match_reasons = compute_job_match(
                    app.student, app.job
                )

                interviews = Interview.objects.filter(
                    application=app
                ).order_by("-interview_date")

                interview_history = [
                    {
                        "id": iv.id,
                        "date": iv.interview_date,
                        "mode": iv.get_interview_mode_display(),
                        "status": iv.get_status_display(),
                        "remarks": iv.remarks,
                    }
                    for iv in interviews
                ]

                # If this specific application doesn't have a
                # resume attached (e.g. the student applied
                # before uploading one), fall back to whatever
                # resume is currently active on their account so
                # the company still sees something relevant.

                fallback_resume = None

                if not app.resume:

                    fallback_resume = Resume.objects.filter(
                        student=app.student.user,
                        is_active=True
                    ).first()

                candidates.append({

                    "id": app.id,

                    "name": app.student.full_name,

                    "email": getattr(app.student.user, "email", ""),

                    "phone": getattr(app.student.user, "phone", ""),

                    "location": app.student.location,

                    "age": app.student.age,

                    "gender": app.student.gender,

                    "job_id": app.job_id,

                    "job_title": app.job.title,

                    "status": app.status,

                    "status_display": app.get_status_display(),

                    "applied_on": app.applied_date,

                    "cover_letter": app.cover_letter,

                    "career_interest": app.student.career_interest,

                    "course": app.student.course,

                    "department": app.student.department,

                    "institution": app.student.institution,

                    "graduation_year": app.student.graduation_year,

                    "cgpa": app.student.ug_cgpa,

                    "backlog_count": app.student.backlog_count,

                    "skills": app.student.skills,

                    "experience": app.student.experience,

                    "internships": app.student.internships,

                    "projects": app.student.projects,

                    "certifications": app.student.certifications,

                    "linkedin": app.student.linkedin,

                    "github": app.student.github,

                    "portfolio": app.student.portfolio,

                    "resume_url": (
                        request.build_absolute_uri(app.resume.file.url)
                        if app.resume and app.resume.file
                        else (
                            request.build_absolute_uri(fallback_resume.file.url)
                            if fallback_resume and fallback_resume.file
                            else None
                        )
                    ),

                    "resume_score": (
                        app.resume.resume_score
                        if app.resume
                        else (fallback_resume.resume_score if fallback_resume else None)
                    ),

                    "resume_skills": (
                        app.resume.skills
                        if app.resume
                        else (fallback_resume.skills if fallback_resume else [])
                    ),

                    "match_score": match_score,

                    "match_reasons": match_reasons,

                    "recruiter_notes": app.recruiter_notes,

                    "interview_history": interview_history,

                })

            except Exception as e:

                print("Error building candidate row for application", app.id, ":", e)

                continue


        thirty_days_ago = timezone.now() - timedelta(days=30)


        stats = {

            "total_candidates": applications.count(),

            "new_applicants": applications.filter(
                applied_date__gte=thirty_days_ago
            ).count(),

            "shortlisted": applications.filter(
                status="shortlisted"
            ).count(),

            "interview_scheduled": applications.filter(
                status="interview"
            ).count(),

        }


        jobs = list(

            Job.objects.filter(
                company=company
            ).values("id", "title")

        )


        return Response({

            "stats": stats,

            "jobs": jobs,

            "candidates": candidates,

        })


    # =====================================================
# REVIEW CANDIDATE
# =====================================================


class CandidateReviewCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request,application_id):


        application = get_object_or_404(

            Application,

            id=application_id,

            job__company=request.user.company_profile

        )



        serializer = CandidateReviewSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save(

                application=application,

                recruiter=request.user

            )



            return Response(

                {

                    "message":
                    "Candidate reviewed",

                    "data":
                    serializer.data

                },

                status=201

            )



        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# SHORTLIST CANDIDATE
# =====================================================


class ShortlistCandidateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,review_id):


        review = get_object_or_404(

            CandidateReview,

            id=review_id,

            recruiter=request.user

        )



        serializer = CandidateShortlistSerializer(

            review,

            data=request.data,

            partial=True

        )



        if serializer.is_valid():


            serializer.save()



            return Response(

                {

                    "message":
                    "Candidate updated",

                    "data":
                    serializer.data

                }

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# UPDATE APPLICATION STATUS
# =====================================================


class CompanyApplicationStatusView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,application_id):


        application = get_object_or_404(

            Application,

            id=application_id,

            job__company=request.user.company_profile

        )



        serializer = ApplicationStatusSerializer(

            application,

            data=request.data,

            partial=True

        )



        if serializer.is_valid():


            serializer.save(

                updated_by=request.user

            )


            # If this update moved the application to "interview"
            # and no Interview record exists for it yet, create
            # one automatically here - this is what actually makes
            # the Interviews tab show it, since that tab reads from
            # the Interview model, not the application's status
            # field. Without this, picking "Interview Scheduled"
            # from the Candidates page's status dropdown (instead
            # of using the "Schedule Interview" form) changed the
            # status but left the Interviews tab empty, since no
            # Interview row was ever created for that path.
            #
            # The dropdown doesn't collect a date/time/mode, so
            # this uses a placeholder (tomorrow, same time, online)
            # - the recruiter can reschedule it to the real
            # date/time afterward from the Interviews page.

            if application.status == "interview":

                from django.utils import timezone

                from datetime import timedelta

                existing_interview = Interview.objects.filter(

                    application=application

                ).order_by("-interview_date").first()

                if not existing_interview:

                    Interview.objects.create(

                        application=application,

                        interviewer=request.user,

                        interview_date=timezone.now() + timedelta(days=1),

                        interview_mode="online",

                        status="scheduled",

                        remarks=(
                            "Auto-created when status was set to "
                            "'Interview Scheduled' from the Candidates "
                            "page - this date/time is a placeholder. "
                            "Please update it to the real interview "
                            "date/time from the Interviews page."
                        ),

                    )


            # Route through the centralized Notification Engine
            # instead of calling WhatsApp/in-app separately - this
            # is what makes the admin's per-event channel toggles
            # (NotificationChannelSetting) actually take effect.

            status_to_event = {
                "reviewing": "application_under_review",
                "shortlisted": "shortlisted",
                "interview": "interview_scheduled",
                "selected": "selected",
                "rejected": "rejected",
            }

            event_key = status_to_event.get(application.status)

            if event_key:

                try:

                    from jobsystem.services.notification_engine import dispatch

                    dispatch(
                        event_key,
                        application.student.user,
                        {
                            "job_title": application.job.title,
                            "company_name": (
                                application.job.company.company_name
                                if application.job.company else "the company"
                            ),
                        },
                    )

                except Exception as e:

                    print("Notification dispatch error:", e)


            return Response(

                {

                    "message":
                    "Application status updated",

                    "data":
                    serializer.data

                }

            )


        return Response(

            serializer.errors,

            status=400

        )


    # =====================================================
    # RECRUITER NOTES (private, company-only)
    # PATCH /company/candidates/<application_id>/notes/
    # =====================================================


class CompanyCandidateNotesView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def patch(self, request, application_id):

        application = get_object_or_404(
            Application,
            id=application_id,
            job__company=request.user.company_profile
        )

        application.recruiter_notes = request.data.get(
            "recruiter_notes", ""
        )

        application.save()

        return Response({
            "message": "Notes saved",
            "recruiter_notes": application.recruiter_notes,
        })


    # =====================================================
    # NOTIFY STUDENT THEIR PROFILE WAS VIEWED
    # POST /company/candidates/<application_id>/viewed/
    # =====================================================


class CandidateProfileViewedView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def post(self, request, application_id):

        application = get_object_or_404(
            Application,
            id=application_id,
            job__company=request.user.company_profile
        )

        student = application.student

        user = student.user

        from django.utils import timezone

        from datetime import timedelta

        recently_notified = Notification.objects.filter(
            user=user,
            notification_type="application",
            title="Your profile was viewed",
            created_at__gte=timezone.now() - timedelta(hours=6),
        ).filter(
            message__icontains=application.job.title
        ).exists()

        if recently_notified:

            return Response({
                "message": "Student already notified recently",
                "whatsapp_sent": False,
            })

        company_name = (
            request.user.company_profile.company_name
            if hasattr(request.user, "company_profile")
            else "A company"
        )

        message = (
            f"Good news! {company_name} just viewed your profile "
            f"for the '{application.job.title}' role on Vetri Jobs."
        )

        Notification.objects.create(
            user=user,
            title="Your profile was viewed",
            message=message,
            notification_type="application",
        )

        from jobsystem.services.whatsapp import send_whatsapp_message

        whatsapp_sent = False

        try:

            whatsapp_sent = send_whatsapp_message(user, message)

        except Exception as e:

            print("CandidateProfileViewedView whatsapp error:", e)

        return Response({
            "message": "Student notified",
            "whatsapp_sent": whatsapp_sent,
        })


    # =====================================================
    # CREATE INTERVIEW
    # =====================================================


class CompanyInterviewCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        serializer = InterviewCreateSerializer(

            data=request.data

        )



        if serializer.is_valid():


            application = serializer.validated_data["application"]



            if application.job.company != request.user.company_profile:


                return Response(

                    {
                        "error":
                        "Not your candidate"
                    },

                    status=403

                )



            serializer.save(

                interviewer=request.user

            )


            # Scheduling an interview should also move the
            # candidate's application status to "interview" - this
            # was never happening before, which is why the
            # Candidates page kept showing the old status even
            # after an interview was scheduled.
            #
            # Only "selected" (already hired) should block this -
            # a recruiter explicitly scheduling a NEW interview for
            # a previously "rejected" candidate is a deliberate
            # decision to reconsider them, and should be allowed to
            # move the status forward to "interview" again. The old
            # check here also excluded "rejected", which silently
            # meant: once a candidate had ever been rejected,
            # scheduling a fresh interview for them afterward would
            # still create the Interview record, but their
            # application status stayed stuck on "rejected" forever
            # - making that interview permanently invisible on the
            # Interviews tab, since it filters on
            # application status == "interview".

            if application.status != "selected":

                application.status = "interview"

                application.save()


            # Route through the centralized Notification Engine,
            # so the interview_date/time/mode are included exactly
            # as shown in the spec example ("Interview Date: ...
            # Time: ... Mode: ...") and admin channel toggles apply.

            try:

                from jobsystem.services.notification_engine import dispatch

                interview_date = serializer.validated_data.get(
                    "interview_date"
                )

                interview_mode = serializer.validated_data.get(
                    "interview_mode", ""
                )

                dispatch(
                    "interview_scheduled",
                    application.student.user,
                    {
                        "job_title": application.job.title,
                        "company_name": (
                            application.job.company.company_name
                            if application.job.company else "the company"
                        ),
                        "interview_date": (
                            interview_date.strftime("%d %b %Y")
                            if interview_date else "TBA"
                        ),
                        "interview_time": (
                            interview_date.strftime("%I:%M %p")
                            if interview_date else "TBA"
                        ),
                        "mode": interview_mode or "Online",
                    },
                )

            except Exception as e:

                print("Notification dispatch error:", e)


            return Response(

                {

                    "message":
                    "Interview scheduled",

                    "data":
                    serializer.data

                },

                status=201

            )



        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
    # LIST COMPANY INTERVIEWS
    # GET /company/interviews/
    # =====================================================


class CompanyInterviewListView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self, request):

        company = request.user.company_profile

        interviews_qs = Interview.objects.filter(

            application__job__company=company,

            # Only candidates whose application is currently in
            # the "interview" stage belong on this page - once a
            # candidate is later rejected or selected, their old
            # interview record shouldn't keep showing up here as
            # if they're still awaiting interview.
            application__status="interview",

        ).select_related(

            "application", "application__student",
            "application__student__user", "application__job"

        ).order_by("-interview_date")


        interviews = []

        for iv in interviews_qs:

            app = iv.application

            interviews.append({

                "id": iv.id,

                "application_id": app.id,

                "candidate_name": app.student.full_name,

                "candidate_email": getattr(app.student.user, "email", ""),

                "job_title": app.job.title,

                "interview_date": iv.interview_date,

                "interview_mode": iv.get_interview_mode_display(),

                "location": iv.location,

                "meeting_link": iv.meeting_link,

                "status": iv.status,

                "status_display": iv.get_status_display(),

                "remarks": iv.remarks,

            })


        stats = {

            "total": interviews_qs.count(),

            "upcoming": interviews_qs.filter(
                status="scheduled"
            ).count(),

            "completed": interviews_qs.filter(
                status="completed"
            ).count(),

            "cancelled": interviews_qs.filter(
                status="cancelled"
            ).count(),

        }


        jobs = list(

            Job.objects.filter(
                company=company
            ).values("id", "title")

        )


        return Response({

            "stats": stats,

            "jobs": jobs,

            "interviews": interviews,

        })


    # =====================================================
    # UPDATE INTERVIEW STATUS
    # PATCH /company/interviews/<id>/status/
    # =====================================================


class CompanyInterviewStatusUpdateView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def patch(self, request, interview_id):

        interview = get_object_or_404(

            Interview,

            id=interview_id,

            application__job__company=request.user.company_profile

        )

        new_status = request.data.get("status")

        if new_status not in dict(Interview.STATUS_CHOICES):

            return Response(
                {
                    "error":
                    "Invalid status"
                },
                status=400
            )

        interview.status = new_status

        interview.save()

        return Response(
            {
                "message":
                "Interview status updated",
                "status":
                interview.status,
            }
        )

    from django.db.models import Count, Q


from .models import (

    StudentProfile,

    CompanyProfile,

    PlacementDrive,

    Application,

    Notification,

    PlatformAnalytics,

    User

)


from .serializers import (

    StudentProfileSerializer,

    CompanyProfileSerializer,

    PlacementDriveSerializer,

    PlacementDriveCreateSerializer,

    ApplicationSerializer,

    NotificationCreateSerializer,

    PlatformAnalyticsSerializer

)

# =====================================================
# PLACEMENT ADMIN ACCESS CHECK
# =====================================================


def is_placement_admin(user):

    return user.role == "placement_admin"


# =====================================================
# PLACEMENT ADMIN DASHBOARD
# GET /placement/dashboard/
# =====================================================


class PlacementDashboardView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        from calendar import month_abbr


        total_students = StudentProfile.objects.count()

        active_students = StudentProfile.objects.filter(
            verified=True
        ).count()

        total_companies = CompanyProfile.objects.count()

        active_jobs = Job.objects.filter(status="active").count()

        total_applications = Application.objects.count()

        total_interviews = Interview.objects.count()

        selected_candidates = Application.objects.filter(
            status="selected"
        ).count()

        placement_percentage = (
            round((selected_candidates / total_students) * 100, 1)
            if total_students else 0
        )


        # ---------------- DEPARTMENT-WISE PLACEMENTS ----------------

        dept_counts = (
            Application.objects.filter(status="selected")
            .exclude(student__department="")
            .values("student__department")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        department_placements = [
            {"department": row["student__department"], "count": row["total"]}
            for row in dept_counts
        ]


        # ---------------- COMPANY-WISE HIRING ----------------

        company_counts = (
            Application.objects.filter(status="selected")
            .values("job__company__company_name")
            .annotate(total=Count("id"))
            .order_by("-total")[:6]
        )

        company_hiring = [
            {
                "company": row["job__company__company_name"] or "Unknown",
                "count": row["total"],
            }
            for row in company_counts
        ]


        # ---------------- MONTHLY APPLICATIONS (last 6 months) ----------------

        today = timezone.now().date()

        monthly_applications = []

        for i in range(5, -1, -1):

            year = today.year
            month = today.month - i

            while month <= 0:

                month += 12

                year -= 1

            count = Application.objects.filter(
                applied_date__year=year,
                applied_date__month=month,
            ).count()

            monthly_applications.append({
                "month": f"{month_abbr[month]} '{str(year)[2:]}",
                "count": count,
            })


        # ---------------- SELECTION CONVERSION FUNNEL ----------------

        selection_conversion = [
            {"stage": "Applications", "count": total_applications},
            {
                "stage": "Interviews",
                "count": Application.objects.filter(
                    status__in=["interview", "selected", "rejected"]
                ).count() or total_interviews,
            },
            {
                "stage": "Shortlisted",
                "count": Application.objects.filter(
                    status__in=["shortlisted", "interview", "selected"]
                ).count(),
            },
            {"stage": "Selected", "count": selected_candidates},
        ]


        # ---------------- JOB-WISE APPLICATIONS ----------------

        job_counts = (
            Application.objects.values("job__title")
            .annotate(total=Count("id"))
            .order_by("-total")[:6]
        )

        job_wise_applications = [
            {"job_title": row["job__title"], "count": row["total"]}
            for row in job_counts
        ]


        # ---------------- PLACEMENT TRENDS (last 6 months) ----------------

        placement_trends = []

        for i in range(5, -1, -1):

            year = today.year

            month = today.month - i

            while month <= 0:

                month += 12

                year -= 1

            placed = Application.objects.filter(
                status="selected",
                updated_at__year=year,
                updated_at__month=month,
            ).count()

            applied = Application.objects.filter(
                applied_date__year=year,
                applied_date__month=month,
            ).count()

            rate = round((placed / applied) * 100, 1) if applied else 0

            placement_trends.append({
                "month": f"{month_abbr[month]} '{str(year)[2:]}",
                "placed": placed,
                "placement_rate": rate,
            })


        # ---------------- RECENT DRIVES ----------------

        recent_drives = []

        for drive in PlacementDrive.objects.select_related(
            "company"
        ).order_by("-drive_date")[:5]:

            drive_applications = Application.objects.filter(
                job__company=drive.company
            )

            recent_drives.append({
                "id": drive.id,
                "title": drive.title,
                "company": drive.company.company_name if drive.company else "",
                "drive_date": drive.drive_date,
                "status": drive.get_status_display(),
                "applied": drive_applications.count(),
                "selected": drive_applications.filter(status="selected").count(),
            })


        # ---------------- STUDENT PLACEMENT STATUS (donut) ----------------

        shortlisted_count = Application.objects.filter(
            status__in=["shortlisted", "interview", "selected"]
        ).values("student").distinct().count()

        applied_students_count = Application.objects.values(
            "student"
        ).distinct().count()

        in_process_count = max(
            0, applied_students_count - shortlisted_count - selected_candidates
        )

        not_placed_count = max(
            0, total_students - selected_candidates - shortlisted_count - in_process_count
        )

        student_placement_status = [
            {"label": "Placed", "count": selected_candidates},
            {"label": "In Process", "count": in_process_count},
            {"label": "Shortlisted", "count": shortlisted_count},
            {"label": "Not Placed", "count": not_placed_count},
        ]


        return Response({

            # flat fields for backward compatibility with the
            # existing dashboard cards
            "total_students": total_students,

            "total_companies": total_companies,

            "active_drives": PlacementDrive.objects.filter(
                status__in=["upcoming", "ongoing"]
            ).count(),

            "placed_students": selected_candidates,

            "placement_percentage": placement_percentage,

            "student_placement_status": student_placement_status,

            "recent_students": [
                {
                    "id": s.id,
                    "full_name": s.full_name,
                    "department": s.department,
                    "verified": s.verified,
                }
                for s in StudentProfile.objects.order_by("-id")[:5]
            ],

            "recent_companies": [
                {
                    "id": c.id,
                    "company_name": c.company_name,
                    "industry": c.industry,
                    "verified": c.verified,
                }
                for c in CompanyProfile.objects.order_by("-id")[:5]
            ],

            "upcoming_drives": [
                {
                    "id": d.id,
                    "title": d.title,
                    "company": d.company.company_name if d.company else "",
                    "drive_date": d.drive_date,
                    "status": d.get_status_display(),
                }
                for d in PlacementDrive.objects.filter(
                    status="upcoming"
                ).order_by("drive_date")[:5]
            ],


            # richer data for the KPI-cards + charts dashboard
            "kpis": {

                "total_students": total_students,

                "active_students": active_students,

                "total_companies": total_companies,

                "active_jobs": active_jobs,

                "applications": total_applications,

                "interviews": total_interviews,

                "selected_candidates": selected_candidates,

                "placement_percentage": placement_percentage,

            },

            "department_placements": department_placements,

            "company_hiring": company_hiring,

            "monthly_applications": monthly_applications,

            "selection_conversion": selection_conversion,

            "job_wise_applications": job_wise_applications,

            "placement_trends": placement_trends,

            "recent_drives": recent_drives,

        })


# =====================================================
# MANAGE STUDENTS
# =====================================================


class PlacementStudentListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Placement admin only"
                },

                status=403

            )



        students = StudentProfile.objects.all()



        serializer = StudentProfileSerializer(

            students,

            many=True

        )


        # StudentProfileSerializer's "resume" field is the old,
        # unused StudentProfile.resume FileField - actual resume
        # uploads (from the Resume Management page / Apply flow)
        # go into the separate, versioned Resume model instead.
        # Overlay each student's real active resume here so this
        # list reflects what students actually uploaded.

        data = list(serializer.data)

        active_resumes = {
            r.student_id: r
            for r in Resume.objects.filter(
                student__in=[s.user_id for s in students],
                is_active=True,
            )
        }

        for item, student in zip(data, students):

            active_resume = active_resumes.get(student.user_id)

            if active_resume and active_resume.file:

                item["resume"] = request.build_absolute_uri(
                    active_resume.file.url
                )

                item["resume_score"] = active_resume.resume_score


        return Response(

            data

        )

    # =====================================================
# VERIFY STUDENT
# =====================================================


class VerifyStudentView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,student_id):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        student=get_object_or_404(

            StudentProfile,

            id=student_id

        )



        student.verified=True

        student.save()


        try:

            from jobsystem.services.notification_engine import dispatch

            dispatch(
                "profile_verification",
                student.user,
                {"name": student.full_name or student.user.username},
            )

        except Exception as e:

            print("VerifyStudentView notification error:", e)


        return Response(

            {
                "message":
                "Student verified successfully"
            }

        )


# =====================================================
# CREATE STUDENT (PLACEMENT ADMIN)
# =====================================================


class PlacementStudentCreateView(APIView):

    """
    POST /placement/students/create/

    Lets a placement admin add a brand new student account
    directly (rather than the student self-registering). Since
    there's no password field on this form, a random temporary
    password is generated - the student can set their own via
    the existing "Forgot Password" OTP flow on first login.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        if request.user.role != "placement_admin":

            return Response(
                {"error": "Only placement admins can add students."},
                status=403,
            )

        full_name = (request.data.get("full_name") or "").strip()

        email = (request.data.get("email") or "").strip()

        phone = (request.data.get("phone") or "").strip()

        if not full_name or not email:

            return Response(
                {"error": "Full name and email are required."},
                status=400,
            )

        try:

            import secrets

            temp_password = secrets.token_urlsafe(12)

            base_username = email.split("@")[0]

            username = base_username

            suffix = 1

            while User.objects.filter(username__iexact=username).exists():

                suffix += 1

                username = f"{base_username}{suffix}"

            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                role="student",
                phone=phone,
            )

            student = StudentProfile.objects.create(

                user=user,

                full_name=full_name,

                phone=phone,

                student_id=request.data.get("student_id") or None,

                gender=request.data.get("gender") or "",

                location=request.data.get("location") or "",

            )

            return Response(
                {
                    "message": "Student added successfully.",
                    "id": student.id,
                    "user_id": user.id,
                },
                status=201,
            )

        except Exception as e:

            import traceback

            traceback.print_exc()

            print("PlacementStudentCreateView error:", repr(e))

            error_text = str(e).lower()

            if "unique" in error_text and "email" in error_text:

                friendly_message = "A student with this email already exists."

            elif "unique" in error_text and "username" in error_text:

                friendly_message = "That username is already taken."

            elif "unique" in error_text and "student_id" in error_text:

                friendly_message = (
                    "That Student ID is already in use by another student."
                )

            else:

                friendly_message = "Could not add student. Please try again."

            response_data = {"error": friendly_message}

            if settings.DEBUG:

                # Surface the real exception in local/dev so it doesn't
                # have to be dug out of the server console every time.
                response_data["debug_detail"] = str(e)

            return Response(
                response_data,
                status=400,
            )


# =====================================================
# UPDATE STUDENT PROFILE (PLACEMENT ADMIN)
# =====================================================


class PlacementStudentUpdateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]


    def patch(self,request,student_id):


        if not is_placement_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )


        student=get_object_or_404(

            StudentProfile,

            id=student_id

        )


        data = request.data


        editable_fields = [

            "full_name",
            "student_id",
            "gender",
            "location",
            "course",
            "department",
            "graduation_year",
            "ug_cgpa",

        ]


        for field in editable_fields:

            if field in data:

                setattr(student, field, data.get(field))


        student.save()


        phone = data.get("phone")

        if phone is not None:

            student.user.phone = phone

            student.user.save()


        serializer = StudentProfileSerializer(student)


        return Response(serializer.data)


class PlacementStudentStatusUpdateView(APIView):

    """
    PATCH /placement/students/<id>/status/
    { "placement_status": "Placed" | "Not Placed" | "Looking" }

    Powers the "Mark Placed" / "Mark Not Placed" quick-action
    buttons on the Students page.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, student_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403,
            )

        student = get_object_or_404(
            StudentProfile,
            id=student_id,
        )

        new_status = request.data.get("placement_status")

        valid_statuses = [
            choice[0]
            for choice in StudentProfile.PLACEMENT_STATUS_CHOICES
        ]

        if new_status not in valid_statuses:

            return Response(
                {
                    "error":
                    f"placement_status must be one of {valid_statuses}"
                },
                status=400,
            )

        student.placement_status = new_status

        student.save()

        serializer = StudentProfileSerializer(student)

        return Response(serializer.data)


    # =====================================================
# COMPANY LIST
# =====================================================


class PlacementCompanyHistoryView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self,request,company_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        company = CompanyProfile.objects.filter(id=company_id).first()

        if not company:

            return Response(
                {"error": "Company not found"},
                status=404
            )

        applications = Application.objects.filter(
            job__company=company
        )

        interviewed_count = applications.filter(
            status__in=["interview", "selected", "rejected"]
        ).count()

        selected_count = applications.filter(
            status="selected"
        ).count()

        drives = PlacementDrive.objects.filter(
            company=company
        ).order_by("-drive_date")

        previous_drives = [
            {
                "id": d.id,
                "title": d.title,
                "drive_date": d.drive_date,
                "status": d.get_status_display(),
                "vacancies": d.vacancies,
                "applied": Application.objects.filter(
                    job=d.job
                ).count() if d.job else 0,
                "selected": Application.objects.filter(
                    job=d.job, status="selected"
                ).count() if d.job else 0,
            }
            for d in drives
        ]

        from django.db.models.functions import TruncMonth

        from django.db.models import Count

        historical_hiring = list(
            applications.filter(
                status="selected"
            ).annotate(
                month=TruncMonth("applied_date")
            ).values("month").annotate(
                total=Count("id")
            ).order_by("month")
        )

        historical_hiring = [
            {
                "month": row["month"].strftime("%b %Y") if row["month"] else "",
                "hired": row["total"],
            }
            for row in historical_hiring
        ]

        return Response({
            "company_name": company.company_name,
            "industry": company.industry,
            "total_jobs_posted": Job.objects.filter(company=company).count(),
            "students_hired": selected_count,
            "students_interviewed": interviewed_count,
            "students_selected": selected_count,
            "total_applications": applications.count(),
            "previous_drives": previous_drives,
            "historical_hiring": historical_hiring,
        })


class PlacementJobListView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self,request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        jobs = Job.objects.select_related("company").order_by("-created_at")

        results = [
            {
                "id": j.id,
                "title": j.title,
                "company_name": j.company.company_name if j.company else "",
                "company_id": j.company.id if j.company else None,
                "location": j.location,
                "job_type": j.get_job_type_display() if hasattr(j, "get_job_type_display") else j.job_type,
                "status": j.status,
                "applications_count": j.applications.count(),
                "created_at": j.created_at,
            }
            for j in jobs
        ]

        return Response(results)


class PlacementJobStatusUpdateView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def patch(self,request,job_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        job = get_object_or_404(
            Job,
            id=job_id
        )

        previous_status = job.status

        new_status = request.data.get("status")

        valid_statuses = [choice[0] for choice in Job.STATUS_CHOICES]

        if new_status not in valid_statuses:

            return Response(
                {
                    "error":
                    f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                },
                status=400
            )

        job.status = new_status

        job.save()

        # Broadcast a "new job alert" the moment a job first goes
        # live - not on every re-save, only on the pending -> active
        # transition, so students aren't re-notified repeatedly.

        if new_status == "active" and previous_status != "active":

            try:

                from jobsystem.services.notification_engine import dispatch

                students = StudentProfile.objects.filter(
                    verified=True
                ).select_related("user")

                for student in students:

                    dispatch(
                        "new_job_alert",
                        student.user,
                        {
                            "job_title": job.title,
                            "company_name": (
                                job.company.company_name
                                if job.company else "a company"
                            ),
                            "location": job.location or "Not specified",
                        },
                    )

            except Exception as e:

                print("PlacementJobStatusUpdateView new_job_alert error:", e)

        return Response(
            {
                "message": f"Job marked as {new_status}",
                "status": job.status
            }
        )


class PlacementCompanyListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_placement_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        companies = CompanyProfile.objects.all()



        serializer = CompanyProfileSerializer(

            companies,

            many=True,

            context={"request": request}

        )



        return Response(

            serializer.data

        )


    def post(self,request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        data = request.data

        required = ["company_name", "email", "password"]

        missing = [f for f in required if not data.get(f)]

        if missing:

            return Response(
                {"error": "Missing required fields: " + ", ".join(missing)},
                status=400
            )

        if User.objects.filter(email=data.get("email")).exists():

            return Response(
                {"error": "A user with this email already exists."},
                status=400
            )

        try:

            with transaction.atomic():

                user = User.objects.create_user(
                    username=data.get("username") or data.get("email").split("@")[0],
                    email=data.get("email"),
                    password=data.get("password"),
                    role="company",
                )

                company = CompanyProfile.objects.create(
                    user=user,
                    company_name=data.get("company_name"),
                    industry=data.get("industry", ""),
                    website=data.get("website", ""),
                    description=data.get("description", ""),
                    address=data.get("location", ""),
                    contact_email=data.get("contact_email", data.get("email")),
                    phone=data.get("phone", ""),
                    hr_contact_name=data.get("hr_contact_name", ""),
                    company_type=data.get("company_type", ""),
                    verified=True,
                )

        except Exception as e:

            return Response(
                {"error": "Could not create company: " + str(e)},
                status=400
            )

        serializer = CompanyProfileSerializer(
            company,
            context={"request": request}
        )

        return Response(
            serializer.data,
            status=201
        )

    # =====================================================
# VERIFY COMPANY
# =====================================================


class VerifyCompanyView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,company_id):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        company=get_object_or_404(

            CompanyProfile,

            id=company_id

        )



        company.verified=True

        company.approval_status="approved"


        company.save()



        return Response(

            {
                "message":
                "Company verified"
            }

        )

    # =====================================================
# REJECT COMPANY REGISTRATION
# =====================================================


class RejectCompanyView(APIView):

    permission_classes=[

        IsAuthenticated

    ]

    def patch(self, request, company_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        company = get_object_or_404(
            CompanyProfile,
            id=company_id
        )

        company.verified = False

        company.approval_status = "rejected"

        company.rejection_reason = request.data.get("reason", "")

        company.save()

        return Response(
            {
                "message": "Company application rejected"
            }
        )

    # =====================================================
# CREATE DRIVE
# =====================================================


class CreatePlacementDriveView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Placement admin only"
                },

                status=403

            )



        serializer = PlacementDriveCreateSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save(

                created_by=request.user

            )


            return Response(

                {

                    "message":
                    "Placement drive created",

                    "data":
                    serializer.data

                },

                status=201

            )



        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# PLACEMENT DRIVES
# =====================================================


def _normalize_drive_payload(data):
    """
    The Placement Drives UI sends company_name/job_title/eligibility
    as plain strings (not FK ids). This resolves them to the real
    company/job FKs (and the correct model field names) so the
    strict serializer below can validate them normally - without
    needing to touch the existing 1000+ line Drives.jsx form.
    """

    data = data.copy() if hasattr(data, "copy") else dict(data)

    company_name = data.get("company_name")

    if company_name and not data.get("company"):

        company = CompanyProfile.objects.filter(
            company_name__iexact=str(company_name).strip()
        ).first()

        if not company:

            company = CompanyProfile.objects.filter(
                company_name__icontains=str(company_name).strip()
            ).first()

        if company:

            data["company"] = company.id

    job_title = data.get("job_title")

    if job_title and not data.get("job") and data.get("company"):

        job = Job.objects.filter(
            company_id=data["company"],
            title__iexact=str(job_title).strip()
        ).first()

        if job:

            data["job"] = job.id

    if not data.get("title") and job_title:

        data["title"] = job_title

    if data.get("eligibility") and not data.get("eligibility_criteria"):

        data["eligibility_criteria"] = data["eligibility"]

    return data



class PlacementDriveListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        drives = PlacementDrive.objects.all().order_by("-drive_date")



        serializer = PlacementDriveSerializer(

            drives,

            many=True

        )



        return Response(

            serializer.data

        )


    def post(self, request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Placement admin only"},
                status=403
            )

        payload = _normalize_drive_payload(request.data)

        serializer = PlacementDriveCreateSerializer(
            data=payload
        )

        if serializer.is_valid():

            drive = serializer.save(
                created_by=request.user
            )

            return Response(
                {
                    "message": "Placement drive created",
                    "data": PlacementDriveSerializer(drive).data,
                },
                status=201
            )

        return Response(
            serializer.errors,
            status=400
        )


    # =====================================================
    # SINGLE DRIVE - GET / UPDATE / DELETE
    # =====================================================


class PlacementDriveDetailView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self, request, drive_id):

        drive = get_object_or_404(
            PlacementDrive,
            id=drive_id
        )

        return Response(
            PlacementDriveSerializer(drive).data
        )

    def put(self, request, drive_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Placement admin only"},
                status=403
            )

        drive = get_object_or_404(
            PlacementDrive,
            id=drive_id
        )

        payload = _normalize_drive_payload(request.data)

        serializer = PlacementDriveCreateSerializer(
            drive,
            data=payload,
            partial=True
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                {
                    "message": "Placement drive updated",
                    "data": PlacementDriveSerializer(drive).data,
                }
            )

        return Response(
            serializer.errors,
            status=400
        )

    def patch(self, request, drive_id):

        return self.put(request, drive_id)

    def delete(self, request, drive_id):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Placement admin only"},
                status=403
            )

        drive = get_object_or_404(
            PlacementDrive,
            id=drive_id
        )

        drive.delete()

        return Response({
            "message": "Placement drive deleted"
        })
    # =====================================================
# ALL APPLICATIONS
# =====================================================


class PlacementApplicationListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        applications = Application.objects.all()



        serializer = ApplicationSerializer(

            applications,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# PLACEMENT STATUS UPDATE
# =====================================================


    # =====================================================
    # CANDIDATE PIPELINE (placement-wide, across all companies)
    # GET /placement/candidates/pipeline/
    # =====================================================


class PlacementCandidatePipelineView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def get(self, request):

        from django.utils import timezone

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        applications = Application.objects.select_related(
            "student", "student__user", "job", "job__company", "resume"
        ).order_by("-applied_date")

        candidates = []

        for app in applications:

            candidates.append({
                "id": app.id,
                "student_name": app.student.full_name,
                "student_code": f"VJ{app.student.id:07d}",
                "department": app.student.department,
                "cgpa": app.student.ug_cgpa,
                "resume_score": (
                    app.resume.resume_score if app.resume else None
                ),
                "applied_job": app.job.title,
                "company": (
                    app.job.company.company_name
                    if app.job.company else ""
                ),
                "status": app.status,
                "status_display": app.get_status_display(),
                "applied_on": app.applied_date,
            })

        stats = {
            "total_applicants": applications.count(),
            "shortlisted": applications.filter(
                status="shortlisted"
            ).count(),
            "interviews_scheduled": Interview.objects.filter(
                status="scheduled"
            ).count(),
            "final_selected": applications.filter(
                status="selected"
            ).count(),
            "joined": applications.filter(
                status="selected"
            ).count(),
        }

        pipeline_overview = [
            {"stage": "Registration", "count": applications.count()},
            {
                "stage": "Shortlisted",
                "count": applications.filter(
                    status__in=["shortlisted", "interview", "selected"]
                ).count(),
            },
            {
                "stage": "Interview",
                "count": applications.filter(
                    status__in=["interview", "selected"]
                ).count(),
            },
            {
                "stage": "Selected",
                "count": applications.filter(status="selected").count(),
            },
        ]

        today_interviews = [
            {
                "id": iv.id,
                "candidate_name": iv.application.student.full_name,
                "job_title": iv.application.job.title,
                "time": iv.interview_date.strftime("%I:%M %p"),
                "mode": iv.get_interview_mode_display(),
            }
            for iv in Interview.objects.filter(
                interview_date__date=timezone.now().date(),
                status="scheduled",
            ).select_related(
                "application__student", "application__job"
            ).order_by("interview_date")
        ]

        return Response({
            "stats": stats,
            "pipeline_overview": pipeline_overview,
            "candidates": candidates,
            "today_interviews": today_interviews,
        })


class PlacementUpdateApplicationView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,application_id):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        application=get_object_or_404(

            Application,

            id=application_id

        )



        application.status = request.data.get(

            "status"

        )



        application.updated_by=request.user



        application.save()



        return Response(

            {

                "message":
                "Application updated",

                "status":
                application.status

            }

        )

    # =====================================================
# SEND NOTIFICATION
# =====================================================


class PlacementNotificationCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        serializer = NotificationCreateSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save()



            return Response(

                {

                    "message":
                    "Notification sent"

                },

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )


class SendNotificationView(APIView):

    """
    Bulk-send a notification to students through one or more
    channels: in-app (Notification row), email, and/or
    WhatsApp (reusing the existing send_whatsapp_message
    service). Used by the Placement Admin "Send Notifications"
    page.
    """

    permission_classes=[

        IsAuthenticated

    ]

    def post(self,request):

        if not (is_placement_admin(request.user) or is_super_admin(request.user)):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        title = request.data.get("title","").strip()

        message = request.data.get("message","").strip()

        channels = request.data.get("channels") or ["app"]

        audience = request.data.get("audience","all_students")

        student_ids = request.data.get("student_ids") or []

        if not title or not message:

            return Response(
                {"error": "Title and message are required"},
                status=400
            )

        students = StudentProfile.objects.select_related("user")

        if audience == "specific" and student_ids:

            students = students.filter(id__in=student_ids)

        notified_count = 0

        email_sent_count = 0

        whatsapp_sent_count = 0

        from django.core.mail import send_mail

        from django.conf import settings as dj_settings

        from jobsystem.services.whatsapp import send_whatsapp_message

        for student in students:

            user = student.user

            notif = None

            if "app" in channels:

                notif = Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    notification_type="placement",
                )

                notified_count += 1

            if "email" in channels and user.email:

                try:

                    send_mail(

                        title,

                        message,

                        getattr(dj_settings, "DEFAULT_FROM_EMAIL", None),

                        [user.email],

                        fail_silently=False,

                    )

                    email_sent_count += 1

                except Exception as e:

                    print("SendNotificationView email error:", e)

            if "whatsapp" in channels:

                try:

                    sent = send_whatsapp_message(user, message)

                    if sent:

                        whatsapp_sent_count += 1

                        if notif:

                            notif.whatsapp_sent = True

                            notif.save()

                except Exception as e:

                    print("SendNotificationView whatsapp error:", e)

        return Response(

            {

                "message": "Notification processed",

                "total_students": students.count(),

                "app_notified": notified_count,

                "email_sent": email_sent_count,

                "whatsapp_sent": whatsapp_sent_count,

            }

        )


    # =====================================================
# PLACEMENT REPORTS
# =====================================================


from .models import ReportSchedule

from .serializers import ReportScheduleSerializer


class ScheduleReportView(APIView):

    """
    Lets a placement admin schedule a recurring emailed
    placement report summary. The actual sending happens via
    the send_scheduled_reports management command, which
    should be run daily by a scheduler (cron / Task Scheduler).
    """

    permission_classes=[

        IsAuthenticated

    ]

    def get(self, request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        schedule = ReportSchedule.objects.filter(
            created_by=request.user,
            active=True
        ).first()

        if not schedule:

            return Response(None)

        return Response(
            ReportScheduleSerializer(schedule).data
        )

    def post(self, request):

        if not is_placement_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        email = request.data.get("email")

        frequency = request.data.get("frequency", "weekly")

        if not email:

            return Response(
                {"error": "Email is required"},
                status=400
            )

        schedule, created = ReportSchedule.objects.update_or_create(
            created_by=request.user,
            defaults={
                "email": email,
                "frequency": frequency,
                "active": True,
            }
        )

        return Response(
            {
                "message": "Automated report scheduled successfully",
                "data": ReportScheduleSerializer(schedule).data,
            }
        )


class PlacementReportView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_placement_admin(request.user):


            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )


        total_students = StudentProfile.objects.count()

        selected_students = Application.objects.filter(
            status="selected"
        ).count()

        total_companies = CompanyProfile.objects.count()

        placement_percentage = (
            round((selected_students / total_students) * 100, 1)
            if total_students else 0
        )


        company_reports = []

        for company in CompanyProfile.objects.all():

            jobs_count = Job.objects.filter(company=company).count()

            applications_count = Application.objects.filter(
                job__company=company
            ).count()

            hired_count = Application.objects.filter(
                job__company=company,
                status="selected"
            ).count()

            if jobs_count == 0 and hired_count == 0:

                continue

            company_reports.append({
                "id": company.id,
                "name": company.company_name,
                "industry": company.industry,
                "jobs": jobs_count,
                "applications": applications_count,
                "hired": hired_count,
            })

        company_reports.sort(key=lambda c: c["hired"], reverse=True)


        # ---------------- APPLICATION STATUS BREAKDOWN ----------------

        status_breakdown = [
            {
                "status": label,
                "count": Application.objects.filter(status=key).count(),
            }
            for key, label in Application.STATUS_CHOICES
        ] if hasattr(Application, "STATUS_CHOICES") else []


        # ---------------- PLACEMENT BY INDUSTRY ----------------

        from django.db.models import Count

        industry_rows = (
            CompanyProfile.objects.exclude(
                industry__isnull=True
            ).exclude(
                industry__exact=""
            ).values("industry")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        placement_by_industry = [
            {"industry": row["industry"], "count": row["total"]}
            for row in industry_rows
        ]


        # ---------------- MONTHLY PLACEMENT TREND (last 6 months) ----------------

        from django.utils import timezone
        from datetime import timedelta
        import calendar

        placement_trend = []

        today = timezone.now()

        for i in range(5, -1, -1):

            month_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) if i == 0 else today

            year = today.year

            month = today.month - i

            while month <= 0:
                month += 12
                year -= 1

            applications_count = Application.objects.filter(
                applied_date__year=year,
                applied_date__month=month,
            ).count()

            placed_count = Application.objects.filter(
                applied_date__year=year,
                applied_date__month=month,
                status="selected",
            ).count()

            placement_trend.append({
                "month": f"{calendar.month_abbr[month]}",
                "applications": applications_count,
                "placed": placed_count,
            })


        # ---------------- RECENT PLACEMENT ACTIVITY ----------------

        recent_activity = [
            {
                "id": app.id,
                "date": app.applied_date,
                "student_name": app.student.full_name if app.student else "",
                "company_name": (
                    app.job.company.company_name
                    if app.job and app.job.company else ""
                ),
                "status": app.get_status_display(),
            }
            for app in Application.objects.select_related(
                "student", "job", "job__company"
            ).order_by("-applied_date")[:6]
        ]


        drive_reports = []

        for drive in PlacementDrive.objects.select_related(
            "company", "job"
        ).order_by("-drive_date"):

            selected_count = Application.objects.filter(
                job__company=drive.company,
                status="selected"
            ).count()

            drive_reports.append({
                "id": drive.id,
                "company_name": drive.company.company_name if drive.company else "",
                "job_title": drive.job.title if drive.job else drive.title,
                "selected": selected_count,
            })


        data={


            "total_students":

            total_students,



            "verified_students":

            StudentProfile.objects.filter(

                verified=True

            ).count(),




            "total_companies":

            total_companies,



            "companies":

            total_companies,



            "verified_companies":

            CompanyProfile.objects.filter(

                verified=True

            ).count(),




            "total_jobs":

            Job.objects.count(),




            "total_applications":

            Application.objects.count(),




            "selected_students":

            selected_students,



            "placed_students":

            selected_students,



            "unplaced_students":

            max(total_students - selected_students, 0),



            "placement_percentage":

            placement_percentage,



            "company_reports":

            company_reports,



            "drive_reports":

            drive_reports,

            "status_breakdown": status_breakdown,

            "placement_by_industry": placement_by_industry,

            "placement_trend": placement_trend,

            "recent_activity": recent_activity,


        }



        return Response(

            data

        )

    from django.contrib.auth import get_user_model


from .models import (

    Permission,

    RolePermission,

    CustomRole,

    AuditLog,

    PlatformAnalytics,

    AdminSetting,

    SystemSetting,

    CMSContent,

    Job,

    StudentProfile,

    CompanyProfile

)



from .serializers import (

    UserSerializer,

    PermissionSerializer,

    RolePermissionSerializer,

    CustomRoleSerializer,

    AuditLogSerializer,

    PlatformAnalyticsSerializer,

    AdminSettingSerializer,

    SystemSettingSerializer,

    CMSContentSerializer,

    JobSerializer,

    StudentProfileSerializer,

    CompanyProfileSerializer

)


User=get_user_model()

# =====================================================
# SUPER ADMIN CHECK
# =====================================================


def is_super_admin(user):

    return user.role == "super_admin"


# =====================================================
# SUPER ADMIN DASHBOARD
# GET /admin/dashboard/
# =====================================================


class AdminDashboardView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        if not is_super_admin(request.user):

            return Response(
                {"error": "Access denied"},
                status=403
            )

        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count

        thirty_days_ago = timezone.now() - timedelta(days=30)

        total_users = User.objects.count()

        total_students = StudentProfile.objects.count()

        total_companies = CompanyProfile.objects.count()

        total_jobs = Job.objects.count()

        active_jobs = Job.objects.filter(status="active").count()

        total_applications = Application.objects.count()

        selected_candidates = Application.objects.filter(
            status="selected"
        ).count()

        placement_percentage = (
            round((selected_candidates / total_students) * 100, 1)
            if total_students else 0
        )

        new_users_30d = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()

        recent_audit_logs = []

        try:

            recent_audit_logs = [
                {
                    "id": log.id,
                    "user": str(log.user) if log.user else "System",
                    "action": log.action,
                    "created_at": log.created_at,
                }
                for log in AuditLog.objects.order_by("-created_at")[:8]
            ]

        except Exception as e:

            print("Audit log fetch error:", e)

        role_breakdown = list(
            User.objects.values("role")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        return Response({

            # flat fields for backward compatibility with the
            # existing dashboard cards
            "total_users": total_users,

            "students": total_students,

            "companies": total_companies,

            "admins": User.objects.filter(
                role__in=["placement_admin", "super_admin"]
            ).count(),

            "active_jobs": active_jobs,

            "applications": total_applications,

            "recent_users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "date_joined": u.date_joined,
                }
                for u in User.objects.order_by("-date_joined")[:6]
            ],


            # richer data
            "kpis": {

                "total_users": total_users,

                "total_students": total_students,

                "total_companies": total_companies,

                "total_jobs": total_jobs,

                "active_jobs": active_jobs,

                "total_applications": total_applications,

                "selected_candidates": selected_candidates,

                "placement_percentage": placement_percentage,

                "new_users_30d": new_users_30d,

            },

            "role_breakdown": role_breakdown,

            "recent_audit_logs": recent_audit_logs,

        })


# =====================================================
# USER MANAGEMENT
# =====================================================


class AdminUserListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Super admin only"
                },

                status=403

            )


        users = User.objects.all()



        serializer = UserSerializer(

            users,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# UPDATE USER
# =====================================================


class AdminUserUpdateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,user_id):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        user=get_object_or_404(

            User,

            id=user_id

        )



        serializer=UserSerializer(

            user,

            data=request.data,

            partial=True

        )


        if serializer.is_valid():

            serializer.save()



            return Response(

                {
                    "message":
                    "User updated",

                    "data":
                    serializer.data

                }

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# DELETE USER
# =====================================================


class AdminDeleteUserView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def delete(self,request,user_id):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        user=get_object_or_404(

            User,

            id=user_id

        )



        user.delete()



        return Response(

            {
                "message":
                "User deleted"
            }

        )

    # =====================================================
# CREATE PERMISSION
# =====================================================


class PermissionCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )


        serializer=PermissionSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()


            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# LIST PERMISSIONS
# =====================================================


class PermissionListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        permissions=Permission.objects.all()



        serializer=PermissionSerializer(

            permissions,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# ROLE PERMISSION
# =====================================================


class RolePermissionCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )


        serializer=RolePermissionSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()


            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# CUSTOM ROLES
# =====================================================


class CustomRoleListCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        roles=CustomRole.objects.all()



        serializer=CustomRoleSerializer(

            roles,

            many=True

        )



        return Response(

            serializer.data

        )




    def post(self,request):


        serializer=CustomRoleSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()



            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# ADMIN STUDENTS
# =====================================================


class AdminStudentListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        students=StudentProfile.objects.all()



        serializer=StudentProfileSerializer(

            students,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# ADMIN COMPANIES
# =====================================================


class AdminCompanyListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        companies=CompanyProfile.objects.all()



        serializer=CompanyProfileSerializer(

            companies,

            many=True,

            context={"request": request}

        )



        return Response(

            serializer.data

        )

    # =====================================================
# ADMIN JOBS
# =====================================================


class AdminJobListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        jobs=Job.objects.all()



        serializer=JobSerializer(

            jobs,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# ADMIN ANALYTICS
# =====================================================


class AdminAnalyticsView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        data={


            "users":

            User.objects.count(),



            "students":

            StudentProfile.objects.count(),



            "companies":

            CompanyProfile.objects.count(),



            "jobs":

            Job.objects.count(),



            "verified_students":

            StudentProfile.objects.filter(

                verified=True

            ).count(),



            "verified_companies":

            CompanyProfile.objects.filter(

                verified=True

            ).count()

        }



        return Response(

            data

        )

    # =====================================================
# AUDIT LOGS
# =====================================================


class AdminAuditLogView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        if not is_super_admin(request.user):

            return Response(

                {
                    "error":
                    "Access denied"
                },

                status=403

            )



        logs=AuditLog.objects.all()



        serializer=AuditLogSerializer(

            logs,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# SYSTEM SETTINGS
# =====================================================


class SystemSettingView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        settings=SystemSetting.objects.all()



        serializer=SystemSettingSerializer(

            settings,

            many=True

        )


        return Response(

            serializer.data

        )





    def post(self,request):


        serializer=SystemSettingSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()



            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    from django.utils import timezone


from .models import (

    Notification,

    ChatConversation,

    ChatMessage,

    ChatbotSetting,

    WhatsAppSetting,

    WhatsAppMessage,

    CMSContent,

    AuditLog

)



from .serializers import (

    NotificationSerializer,

    NotificationCreateSerializer,

    ChatConversationSerializer,

    ChatMessageSerializer,

    ChatbotSettingSerializer,

    WhatsAppSettingSerializer,

    WhatsAppMessageSerializer,

    CMSContentSerializer

)
# =====================================================
# USER NOTIFICATIONS
# =====================================================


class NotificationListView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        notifications = Notification.objects.filter(

            user=request.user

        )



        serializer = NotificationSerializer(

            notifications,

            many=True

        )


        return Response(

            serializer.data

        )

    # =====================================================
# MARK NOTIFICATION READ
# =====================================================


class NotificationReadView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def patch(self,request,notification_id):


        notification=get_object_or_404(

            Notification,

            id=notification_id,

            user=request.user

        )



        notification.is_read=True


        notification.save()



        return Response(

            {

                "message":

                "Notification marked as read"

            }

        )


class NotificationDeleteView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def delete(self,request,notification_id):

        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )

        notification.delete()

        return Response(
            {
                "message":
                "Notification deleted"
            }
        )


class NotificationMarkAllReadView(APIView):

    permission_classes=[
        IsAuthenticated
    ]

    def patch(self,request):

        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)

        return Response(
            {
                "message":
                "All notifications marked as read"
            }
        )

    # =====================================================
# CREATE NOTIFICATION
# =====================================================


class CreateNotificationView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        if request.user.role not in [

            "placement_admin",

            "super_admin"

        ]:


            return Response(

                {

                "error":

                "Permission denied"

                },

                status=403

            )



        serializer = NotificationCreateSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save()



            return Response(

                {

                "message":

                "Notification created",

                "data":

                serializer.data

                },

                status=201

            )



        return Response(

            serializer.errors,

            status=400

        )


    # =====================================================
    # AI PLACEMENT CHATBOT - unified endpoint
    # POST   /chatbot/          - send a message, get a reply
    # GET    /chatbot/history/  - this user's saved conversation
    # DELETE /chatbot/history/  - clear this user's conversation
    #
    # Reachable without login (AllowAny) so it works on the public
    # landing page for generic questions; personal data is only ever
    # pulled from request.user's own records (see services/chatbot.py).
    # =====================================================


    # =====================================================
    # WHATSAPP CHATBOT (Requirements 20-21)
    # GET  /whatsapp/webhook/  - Meta's verification handshake
    # POST /whatsapp/webhook/  - incoming WhatsApp messages
    #
    # Reuses the exact same generate_reply()/handle_action()
    # logic as the in-app chatbot - the only new part is
    # identifying WHICH student is messaging (by matching
    # their WhatsApp sender number against a registered
    # phone/whatsapp_number), which doubles as the
    # "sensitive actions require authentication" requirement:
    # only a number that matches an existing account can
    # trigger account-specific actions (application status,
    # apply for a job, etc). An unrecognized number gets
    # generic/guest-level answers only, same as a logged-out
    # visitor on the website.
    # =====================================================


class WhatsAppWebhookView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        from jobsystem.models import WhatsAppSetting

        setting = WhatsAppSetting.objects.filter(
            enabled=True
        ).first()

        verify_token = (
            getattr(setting, "verify_token", None) if setting else None
        ) or "vetrijobs"

        mode = request.query_params.get("hub.mode")

        token = request.query_params.get("hub.verify_token")

        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:

            return Response(int(challenge) if challenge else 1)

        return Response({"error": "Verification failed"}, status=403)

    def post(self, request):

        from jobsystem.models import User
        from jobsystem.services.chatbot import generate_reply
        from jobsystem.services.whatsapp import send_whatsapp_message

        try:

            entry = request.data.get("entry", [{}])[0]

            change = entry.get("changes", [{}])[0]

            value = change.get("value", {})

            messages = value.get("messages")

            if not messages:

                # Delivery/read status callbacks land here too -
                # nothing to reply to, just acknowledge.

                return Response({"status": "ignored"})

            incoming = messages[0]

            sender_number = incoming.get("from", "")

            text = (
                incoming.get("text", {}).get("body", "")
                if incoming.get("type") == "text"
                else ""
            )

        except Exception as e:

            print("WhatsApp webhook parse error:", e)

            return Response({"status": "ignored"})

        if not text:

            return Response({"status": "ignored"})

        # Identify the student by their WhatsApp number - this
        # is the "authentication" for sensitive actions: only
        # someone messaging FROM their own registered number
        # can see their own application/interview data, same
        # guarantee as being logged in on the website.

        matched_user = User.objects.filter(
            whatsapp_number__endswith=sender_number[-10:]
        ).first() or User.objects.filter(
            phone__endswith=sender_number[-10:]
        ).first()

        reply = generate_reply(matched_user, text, history=None)

        if not matched_user:

            reply = (
                "I couldn't match this number to a Vetri Jobs account, "
                "so I can only help with general questions here. "
                "Register your WhatsApp number in your profile to unlock "
                "personalized answers about your applications and "
                "interviews.\n\n" + reply
            )

        try:

            fake_user_for_send = matched_user

            if not fake_user_for_send:

                # send_whatsapp_message() looks up the number from
                # the user object - build a throwaway shim so an
                # unmatched sender still gets a reply.

                class _Shim:

                    phone = sender_number

                    whatsapp_number = sender_number

                fake_user_for_send = _Shim()

            send_whatsapp_message(fake_user_for_send, reply)

        except Exception as e:

            print("WhatsApp webhook reply-send error:", e)

        return Response({"status": "ok"})


class ChatbotMessageAPIView(APIView):

    permission_classes = [AllowAny]

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):

        from jobsystem.services.chatbot import (
            generate_reply,
            handle_resume_attachment,
        )
        from jobsystem.models import ChatConversation, ChatMessage

        raw_message = request.data.get("message")

        if isinstance(raw_message, dict):

            raw_message = raw_message.get("message", "")

        user_message = (raw_message or "").strip()

        attachment = request.FILES.get("attachment")

        if not user_message and not attachment:

            return Response(
                {
                    "error":
                    "Message is required"
                },
                status=400
            )

        user = request.user if request.user.is_authenticated else None

        history = []

        conversation = None

        if user:

            conversation, _ = ChatConversation.objects.get_or_create(
                session_id=f"user-{user.id}",
                defaults={"user": user},
            )

            history = [
                {"sender": m.sender, "message": m.message}
                for m in conversation.messages.order_by("-created_at")[:10][::-1]
            ]

            ChatMessage.objects.create(
                conversation=conversation,
                sender="user",
                message=(
                    user_message
                    or f"[Attached file: {getattr(attachment, 'name', 'resume')}]"
                ),
            )

        # -------------------------------------------------
        # ATTACHMENT (resume upload via chat) - only for a
        # signed-in student with a completed profile. Guests
        # and other roles get a clear refusal instead of a
        # silent no-op.
        # -------------------------------------------------

        if attachment:

            profile = getattr(user, "student_profile", None) if user else None

            if not profile:

                reply = (
                    "I can only save resume attachments for a signed-in "
                    "student account. Please log in as a student and "
                    "try again."
                )

            else:

                reply = handle_resume_attachment(
                    user, profile, attachment, caption=user_message
                )

        else:

            reply = generate_reply(
                request.user,
                user_message,
                history=history,
            )

        # generate_reply() (and handle_resume_attachment) normally
        # return a plain string, but the search_jobs/eligible_jobs
        # chatbot actions now return a dict shaped like:
        #   {"reply": "...", "matched_jobs": [...], "navigate_to": "..."}
        # so the frontend can render real job cards with apply links
        # and auto-navigate, instead of just plain text. Only the
        # text portion is ever saved to chat history either way.

        if isinstance(reply, dict):

            reply_text = reply.get("reply", "")

            response_payload = dict(reply)

        else:

            reply_text = reply

            response_payload = {"reply": reply}

        if conversation:

            ChatMessage.objects.create(
                conversation=conversation,
                sender="bot",
                message=reply_text,
            )

        return Response(response_payload)



class ChatbotHistoryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        from jobsystem.models import ChatConversation

        conversation = ChatConversation.objects.filter(
            session_id=f"user-{request.user.id}"
        ).first()

        if not conversation:

            return Response([])

        return Response([
            {
                "sender": m.sender,
                "message": m.message,
                "timestamp": m.created_at,
            }
            for m in conversation.messages.all()
        ])

    def delete(self, request):

        from jobsystem.models import ChatConversation

        ChatConversation.objects.filter(
            session_id=f"user-{request.user.id}"
        ).delete()

        return Response({
            "message":
            "Chat history cleared"
        })


    # =====================================================
    # CREATE CHAT SESSION
    # =====================================================


class ChatConversationCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        import uuid



        conversation = ChatConversation.objects.create(

            user=request.user,

            session_id=str(uuid.uuid4())

        )



        serializer = ChatConversationSerializer(

            conversation

        )


        return Response(

            serializer.data,

            status=201

        )


    # =====================================================
# CHAT MESSAGE
# =====================================================


class ChatMessageCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        conversation_id=request.data.get(

            "conversation"

        )



        message=request.data.get(

            "message"

        )



        conversation=get_object_or_404(

            ChatConversation,

            id=conversation_id,

            user=request.user

        )



        user_message=ChatMessage.objects.create(

            conversation=conversation,

            sender="user",

            message=message

        )





        # AI RESPONSE PLACEHOLDER
        #
        # Later connect:
        # OpenAI API / Gemini API


        bot_reply = (

            "Thank you for your question. "

            "Our career assistant will help you."

        )



        ChatMessage.objects.create(

            conversation=conversation,

            sender="bot",

            message=bot_reply

        )



        return Response(

            {


            "user_message":

            ChatMessageSerializer(

                user_message

            ).data,



            "bot_message":

            bot_reply


            }

        )

    # =====================================================
# CHAT HISTORY
# =====================================================


class ChatHistoryView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request,conversation_id):


        messages=ChatMessage.objects.filter(

            conversation__id=conversation_id,

            conversation__user=request.user

        )



        serializer=ChatMessageSerializer(

            messages,

            many=True

        )



        return Response(

            serializer.data

        )

    # =====================================================
# CHATBOT SETTINGS
# =====================================================


class ChatbotSettingView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        settings=ChatbotSetting.objects.all()



        serializer=ChatbotSettingSerializer(

            settings,

            many=True

        )



        return Response(

            serializer.data

        )




    def post(self,request):


        if request.user.role!="super_admin":


            return Response(

                {

                "error":

                "Admin only"

                },

                status=403

            )



        serializer=ChatbotSettingSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()


            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# WHATSAPP SETTINGS
# =====================================================


class WhatsAppSettingView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        settings=WhatsAppSetting.objects.all()



        serializer=WhatsAppSettingSerializer(

            settings,

            many=True

        )


        return Response(

            serializer.data

        )




    def post(self,request):


        if request.user.role!="super_admin":


            return Response(

                {

                "error":

                "Admin only"

                },

                status=403

            )



        serializer=WhatsAppSettingSerializer(

            data=request.data

        )


        if serializer.is_valid():

            serializer.save()


            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# WHATSAPP MESSAGE LOG
# =====================================================


class WhatsAppMessageCreateView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def post(self,request):


        serializer=WhatsAppMessageSerializer(

            data=request.data

        )



        if serializer.is_valid():


            message=serializer.save()



            # API integration goes here
            #
            # Meta WhatsApp Cloud API
            #



            message.status="sent"

            message.sent_at=timezone.now()

            message.save()



            return Response(

                {

                "message":

                "WhatsApp sent",

                "data":

                serializer.data

                },

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )

    # =====================================================
# CMS CONTENT
# =====================================================


class CMSContentView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        contents=CMSContent.objects.filter(

            is_active=True

        )



        serializer=CMSContentSerializer(

            contents,

            many=True

        )


        return Response(

            serializer.data

        )





    def post(self,request):


        if request.user.role!="super_admin":


            return Response(

                {

                "error":

                "Admin only"

                },

                status=403

            )



        serializer=CMSContentSerializer(

            data=request.data

        )



        if serializer.is_valid():


            serializer.save()



            return Response(

                serializer.data,

                status=201

            )


        return Response(

            serializer.errors,

            status=400

        )
# =====================================================
# RESUME MANAGEMENT API
# =====================================================


class ResumeAPIView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    # GET RESUME

    def get(self,request):


        resume = StudentResume.objects.filter(

            student=request.user,

            is_active=True

        ).last()



        if not resume:


            return Response(

                {},

                status=status.HTTP_200_OK

            )



        serializer=ResumeSerializer(

            resume,

            context={

                "request":request

            }

        )


        return Response(

            serializer.data

        )






    # UPLOAD / REPLACE RESUME


    def post(self,request):


        file=request.FILES.get(

            "resume"

        )


        if not file:


            return Response(

                {

                "error":

                "Resume file required"

                },

                status=400

            )




        # deactivate old resume

        StudentResume.objects.filter(

            student=request.user,

            is_active=True

        ).update(

            is_active=False

        )






        resume=StudentResume.objects.create(


            student=request.user,


            resume=file,


            version=

            StudentResume.objects.filter(

                student=request.user

            ).count()+1


        )




        serializer=ResumeSerializer(

            resume,

            context={

                "request":request

            }

        )



        return Response(

            serializer.data,

            status=201

        )








    # DELETE RESUME


    def delete(self,request):


        StudentResume.objects.filter(

            student=request.user

        ).update(

            is_active=False

        )


        return Response(

            {

            "message":

            "Resume deleted"

            }

        )


    # =====================================================
# STUDENT DASHBOARD
# =====================================================


class StudentDashboardView(APIView):


    permission_classes=[

        IsAuthenticated

    ]



    def get(self,request):


        user=request.user


        # -------------------------------------------------
        # Guard against a missing StudentProfile instead of
        # letting StudentProfile.DoesNotExist bubble up as
        # an unhandled 500 (this was the actual cause of the
        # "Unable to load dashboard" error on the frontend).
        # -------------------------------------------------

        profile = StudentProfile.objects.filter(
            user=user
        ).first()


        if not profile:

            return Response(
                {
                    "error":
                    "Student profile not found. Please "
                    "complete your profile first."
                },
                status=404
            )


        total_jobs = Job.objects.filter(
            status="active"
        ).count()


        # NOTE: Application.student is a FK to StudentProfile,
        # not to the User model - filtering by "student=profile"
        # (not "student=user") so counts are actually correct.

        applied_qs = Application.objects.filter(
            student=profile
        )


        applied_jobs = applied_qs.count()


        shortlisted = applied_qs.filter(
            status="shortlisted"
        ).count()


        interviews = applied_qs.filter(
            status="interview"
        ).count()


        pending = applied_qs.filter(
            status__in=["applied", "reviewing"]
        ).count()


        selected = applied_qs.filter(
            status="selected"
        ).count()


        rejected = applied_qs.filter(
            status="rejected"
        ).count()


        # -------------------------------------------------
        # Recommended jobs - shaped the way the dashboard
        # page renders them (title, company, location,
        # job_type, skills[], match_score)
        # -------------------------------------------------

        applied_job_ids = applied_qs.values_list(
            "job_id", flat=True
        )


        job_qs = Job.objects.filter(
            status="active"
        ).exclude(
            id__in=applied_job_ids
        ).select_related(
            "company"
        )[:30]


        recommended_jobs = []


        scored_jobs = []

        for job in job_qs:

            match_score, match_reasons = compute_job_match(
                profile,
                job
            )

            scored_jobs.append(
                (job, match_score, match_reasons)
            )

        scored_jobs.sort(
            key=lambda item: item[1],
            reverse=True
        )


        for job, match_score, match_reasons in scored_jobs[:5]:

            skills = [
                s.strip()
                for s in (job.skills_required or "").split(",")
                if s.strip()
            ]

            recommended_jobs.append({
                "id": job.id,
                "title": job.title,
                "company": job.company.company_name if job.company else "",
                "location": job.location,
                "job_type": job.get_job_type_display(),
                "skills": skills,
                "match_score": match_score,
                "match_reasons": match_reasons,
            })


        # -------------------------------------------------
        # Recent applications
        # -------------------------------------------------

        recent_applications = []


        for app in applied_qs.select_related(
            "job", "job__company"
        ).order_by("-id")[:5]:

            recent_applications.append({
                "job": app.job.title,
                "company": (
                    app.job.company.company_name
                    if app.job and app.job.company
                    else ""
                ),
                "status": app.get_status_display(),
            })


        # -------------------------------------------------
        # Skills
        # -------------------------------------------------

        skills = list(
            profile.skills_list.values_list(
                "name", flat=True
            )
        )


        # -------------------------------------------------
        # Resume summary (latest active resume, if any)
        # -------------------------------------------------

        resume_obj = Resume.objects.filter(
            student=user,
            is_active=True
        ).first()


        resume_summary = None


        if resume_obj:

            resume_summary = {
                "file_name": resume_obj.filename,
                "score": resume_obj.resume_score,
                "missing": resume_obj.missing_information,
                "skills": resume_obj.skills,
                "job_categories": resume_obj.job_categories,
                "updated_at": resume_obj.updated_at,
            }


        notifications = Notification.objects.filter(

            user=user

        ).values(

            "id",

            "message",

            "created_at"

        )[:5]


               student_skills = [
            s.strip()
            for s in (getattr(profile, "skills", "") or "").split(",")
            if s.strip()
        ]


        # -------------------------------------------------
        # Next upcoming interview (real date/time/mode) - the
        # Dashboard's "Upcoming Interview" card previously tried to
        # infer this from the 5 most recent applications' status
        # text under a "recent_applications" key this view never
        # actually returns (it's "applications"), so it always
        # showed "No upcoming interviews scheduled" regardless of
        # what was really booked. This queries the real Interview
        # record directly instead.
        # -------------------------------------------------

        from django.utils import timezone

        upcoming_interview_obj = Interview.objects.filter(
            application__student=profile,
            interview_date__gte=timezone.now(),
            status__in=["scheduled", "rescheduled"],
        ).select_related(
            "application__job", "application__job__company"
        ).order_by("interview_date").first()

        next_interview = None

        if upcoming_interview_obj:

            next_interview = {
                "job_title": upcoming_interview_obj.application.job.title,
                "company": (
                    upcoming_interview_obj.application.job.company.company_name
                    if upcoming_interview_obj.application.job.company else ""
                ),
                "date": upcoming_interview_obj.interview_date.strftime("%b %d, %Y"),
                "time": upcoming_interview_obj.interview_date.strftime("%I:%M %p"),
                "mode": upcoming_interview_obj.get_interview_mode_display(),
            }


        return Response({


            "profile_completion":

            getattr(profile, "profile_completion", 0),



            "stats": {

                "total_applied": applied_jobs,

                "shortlisted": shortlisted,

                "interview": interviews,

                "pending": pending,

                "offered": selected,

                "rejected": rejected,

            },



            "total_jobs":

            total_jobs,



            "recommended_jobs":

            recommended_jobs,



            "applications":

            recent_applications,



            "skills":

            student_skills,



            "resume":

            resume_summary,



                        "notifications":

            list(notifications),


            "next_interview":

            next_interview



        })

from rest_framework.generics import ListAPIView


from .models import Job

from .serializers import JobSerializer





class JobListAPIView(ListAPIView):


    queryset=Job.objects.filter(

        is_active=True

    )


    serializer_class=JobSerializer

# =====================================================
# STUDENT JOB DETAIL
# =====================================================


# =====================================================
# PUBLIC LOOKUP LISTS (Requirement 28 -> frontend link)
# Read-only, no auth required - these power the dropdowns
# on registration/profile/job-posting forms, and are fully
# controlled by whatever the Super Admin configures in
# Django Admin (Departments / Courses / Job Categories).
# =====================================================


# =====================================================
# SITE BRANDING (public - powers the logo shown in the
# navbar/sidebar everywhere on the frontend, managed from
# Django Admin)
# =====================================================


class SiteBrandingView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        from jobsystem.models import SiteBranding

        branding = SiteBranding.objects.first()

        if not branding:

            return Response({
                "site_name": "Vetri Jobs",
                "tagline": "Career Portal",
                "logo_url": None,
                "favicon_url": None,
                "login_hero_image_url": None,
                "login_headline": "Learn Apply Grow",
                "login_subheadline":
                    "AI-powered placement platform connecting students "
                    "with top opportunities.",
                "register_hero_image_url": None,
                "register_headline": "Your Future Starts Here",
                "register_subheadline":
                    "Join thousands of students and discover your "
                    "dream career.",
                "company_login_hero_image_url": None,
                "company_login_headline": "Hire Top Talent Build Tomorrow",
                "company_login_subheadline":
                    "Connect with skilled students and grow your team.",
                "company_register_hero_image_url": None,
                "company_register_headline": "Let's Build a Better Tomorrow",
                "company_register_subheadline":
                    "Create your company account and start hiring the "
                    "right talent.",
                "placement_login_hero_image_url": None,
                "placement_login_headline": "Manage Placements Create Impact",
                "placement_login_subheadline":
                    "Streamline drives, track progress and empower "
                    "student success.",
                "admin_login_hero_image_url": None,
                "admin_login_headline": "Complete Control Total Visibility",
                "admin_login_subheadline":
                    "Manage every user, role and setting across the "
                    "whole platform.",
                "dashboard_assistant_image_url": None,
                "chatbot_avatar_image_url": None,
                "profile_hero_image_url": None,
                "homepage_badge_text": "AI Powered Placement Portal",
                "homepage_headline": "Smarter Careers",
                "homepage_headline_highlight": "Start Here",
                "homepage_subtext":
                    "Find internships, jobs and placement opportunities "
                    "with the power of AI. Get personalized job matches, "
                    "resume insights and interview preparation - all in "
                    "one platform.",
                "homepage_hero_image_url": None,
            })

        return Response({
            "site_name": branding.site_name,
            "tagline": branding.tagline,
            "logo_url": (
                request.build_absolute_uri(branding.logo.url)
                if branding.logo else None
            ),
            "favicon_url": (
                request.build_absolute_uri(branding.favicon.url)
                if branding.favicon else None
            ),
            "login_hero_image_url": (
                request.build_absolute_uri(branding.login_hero_image.url)
                if branding.login_hero_image else None
            ),
            "login_headline": branding.login_headline,
            "login_subheadline": branding.login_subheadline,
            "register_hero_image_url": (
                request.build_absolute_uri(branding.register_hero_image.url)
                if branding.register_hero_image else None
            ),
            "register_headline": branding.register_headline,
            "register_subheadline": branding.register_subheadline,
            "company_login_hero_image_url": (
                request.build_absolute_uri(branding.company_login_hero_image.url)
                if branding.company_login_hero_image else None
            ),
            "company_login_headline": branding.company_login_headline,
            "company_login_subheadline": branding.company_login_subheadline,
            "company_register_hero_image_url": (
                request.build_absolute_uri(branding.company_register_hero_image.url)
                if branding.company_register_hero_image else None
            ),
            "company_register_headline": branding.company_register_headline,
            "company_register_subheadline": branding.company_register_subheadline,
            "placement_login_hero_image_url": (
                request.build_absolute_uri(branding.placement_login_hero_image.url)
                if branding.placement_login_hero_image else None
            ),
            "placement_login_headline": branding.placement_login_headline,
            "placement_login_subheadline": branding.placement_login_subheadline,
            "admin_login_hero_image_url": (
                request.build_absolute_uri(branding.admin_login_hero_image.url)
                if branding.admin_login_hero_image else None
            ),
            "admin_login_headline": branding.admin_login_headline,
            "admin_login_subheadline": branding.admin_login_subheadline,
            "dashboard_assistant_image_url": (
                request.build_absolute_uri(branding.dashboard_assistant_image.url)
                if branding.dashboard_assistant_image else None
            ),
            "chatbot_avatar_image_url": (
                request.build_absolute_uri(branding.chatbot_avatar_image.url)
                if branding.chatbot_avatar_image else None
            ),
            "profile_hero_image_url": (
                request.build_absolute_uri(branding.profile_hero_image.url)
                if branding.profile_hero_image else None
            ),
            "homepage_badge_text": branding.homepage_badge_text,
            "homepage_headline": branding.homepage_headline,
            "homepage_headline_highlight": branding.homepage_headline_highlight,
            "homepage_subtext": branding.homepage_subtext,
            "homepage_hero_image_url": (
                request.build_absolute_uri(branding.homepage_hero_image.url)
                if branding.homepage_hero_image else None
            ),
        })


class LookupListsView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        from jobsystem.models import Department, Course, JobCategory

        departments = list(
            Department.objects.filter(
                is_active=True
            ).order_by("name").values("id", "name", "code")
        )

        department_id = request.query_params.get("department")

        courses_qs = Course.objects.filter(
            is_active=True
        )

        if department_id:

            courses_qs = courses_qs.filter(
                department_id=department_id
            )

        courses = list(
            courses_qs.order_by("name").values(
                "id", "name", "department_id", "duration_years"
            )
        )

        job_categories = list(
            JobCategory.objects.filter(
                is_active=True
            ).order_by("name").values("id", "name")
        )

        return Response({

            "departments": departments,

            "courses": courses,

            "job_categories": job_categories,

        })


class EligibilityCheckView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request, job_id):

        from jobsystem.services.eligibility import check_eligibility

        job = get_object_or_404(
            Job,
            id=job_id
        )

        profile = getattr(request.user, "student_profile", None)

        if not profile:

            return Response(
                {
                    "error":
                    "Please complete your student profile first."
                },
                status=400
            )

        result = check_eligibility(profile, job)

        result["job_id"] = job.id

        result["job_title"] = job.title

        return Response(result)

    # =====================================================
# DELETE COMPANY JOB
# =====================================================

class CompanyDeleteJobView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def delete(self,request,id):


        try:

            job = Job.objects.get(
                id=id,
                company=request.user.company_profile
            )


            job.delete()


            return Response(
                {
                    "message":
                    "Job deleted successfully"
                },
                status=200
            )


        except Job.DoesNotExist:


            return Response(
                {
                    "error":
                    "Job not found"
                },
                status=404
            )


import os
import json
import time

from django.conf import settings
from django.http import FileResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


from .models import Resume
from .serializers import ResumeSerializer


from .services.resume_ai import analyze_resume


# ==================================
# Upload Resume
# Replace Resume
# ==================================

class ResumeUploadView(APIView):

    permission_classes = [
        IsAuthenticated
    ]


    # -------------------------------------------------
    # GET /student/resume/
    # Returns the student's current ACTIVE resume
    # (added so the Resume Management page can load the
    # currently uploaded resume; nothing above was removed).
    # -------------------------------------------------

    def get(self, request):

        resume = Resume.objects.filter(
            student=request.user,
            is_active=True
        ).first()


        if not resume:

            return Response(
                {
                    "detail":
                    "No resume uploaded yet"
                },
                status=404
            )


        serializer = ResumeSerializer(
            resume,
            context={
                "request":request
            }
        )


        return Response(
            serializer.data
        )


    # -------------------------------------------------
    # POST /student/resume/
    # Uploads a new resume (also used to REPLACE the
    # current resume - the previous one is kept as a
    # version in history, just marked inactive).
    # Accepts either "file" or "resume" as the form field
    # name so older and newer frontend calls both work.
    # -------------------------------------------------

    def post(self, request):

        file = request.FILES.get(
            "file"
        ) or request.FILES.get(
            "resume"
        )


        if not file:

            return Response(
                {
                    "error":
                    "Resume file required"
                },
                status=400
            )


        allowed_extensions = (".pdf", ".doc", ".docx")

        if not file.name.lower().endswith(allowed_extensions):

            return Response(
                {
                    "error":
                    "Only PDF, DOC or DOCX files are allowed."
                },
                status=400
            )


        student = request.user


        # deactivate previous resume

        Resume.objects.filter(
            student=student,
            is_active=True
        ).update(
            is_active=False
        )


        resume = Resume.objects.create(

            student=student,

            file=file,

            filename=file.name,

            is_active=True

        )


        # ==========================
        # AI ANALYSIS
        # ==========================


        try:

            start=time.time()


            # analyze_resume() takes the resume's Django file
            # object (works with any storage backend - local
            # disk or Cloudinary), not a filesystem path.
            # resume.file.path raises NotImplementedError under
            # Cloudinary storage, which is what was silently
            # breaking this in production.

            result = analyze_resume(
                resume.file
            )


            resume.resume_score = result.get(
                "resume_score",
                0
            )


            resume.skills = result.get(
                "skills",
                []
            )


            resume.experience = result.get(
                "experience",
                []
            )


            resume.education = result.get(
                "education",
                []
            )


            resume.certifications = result.get(
                "certifications",
                []
            )


            resume.projects = result.get(
                "projects",
                []
            )


            resume.missing_information = result.get(
                "missing_information",
                []
            )


            resume.job_categories = result.get(
                "job_categories",
                []
            )


            resume.extracted_text = result.get(
                "text",
                ""
            )


            resume.save()



        except Exception as e:


            print(
                "AI Error:",
                e
            )



        serializer = ResumeSerializer(
            resume,
            context={
                "request":request
            }
        )


        return Response(
            serializer.data,
            status=201
        )



# ==================================
# Get Resume List
# ==================================

class ResumeListView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def get(self,request):

        resumes = Resume.objects.filter(
            student=request.user
        )


        serializer = ResumeSerializer(
            resumes,
            many=True,
            context={
                "request":request
            }
        )


        return Response(
            serializer.data
        )



# ==================================
# Download Resume
# ==================================

class ResumeDownloadView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def get(self,request,id):


        resume = Resume.objects.get(
            id=id,
            student=request.user
        )


        return FileResponse(

            resume.file.open(
                "rb"
            ),

            as_attachment=True,

            filename=resume.filename

        )



# ==================================
# Delete Resume
# ==================================

class ResumeDeleteView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def delete(self,request,id):


        resume = Resume.objects.get(
            id=id,
            student=request.user
        )


        # remove file
        #
        # resume.file.delete() goes through Django's Storage
        # API, so it works the same way whether the file lives
        # on local disk or in Cloudinary. os.path.exists()/
        # os.remove() only work for local disk storage and
        # raised NotImplementedError under Cloudinary, which
        # broke every resume deletion in production.

        if resume.file:

            resume.file.delete(save=False)


        resume.delete()


        return Response(
            {
                "message":
                "Resume deleted successfully"
            }
        )



# ==================================
# Manual AI Re-analysis
# ==================================

class ResumeAnalyzeView(APIView):

    permission_classes=[
        IsAuthenticated
    ]


    def post(self,request,id):


        resume = Resume.objects.get(

            id=id,

            student=request.user

        )


        # analyze_resume() takes the resume's Django file object,
        # not a filesystem path - see the note in ResumeUploadView
        # above for why resume.file.path breaks under Cloudinary.

        result = analyze_resume(
            resume.file
        )


        resume.resume_score = result.get(
            "resume_score",
            0
        )


        resume.skills=result.get(
            "skills",
            []
        )


        resume.experience=result.get(
            "experience",
            []
        )


        resume.education=result.get(
            "education",
            []
        )


        resume.certifications=result.get(
            "certifications",
            []
        )


        resume.projects=result.get(
            "projects",
            []
        )


        resume.missing_information=result.get(
            "missing_information",
            []
        )


        resume.job_categories=result.get(
            "job_categories",
            []
        )


        resume.save()



        return Response(

            ResumeSerializer(
                resume,
                context={
                    "request":request
                }
            ).data

        )

# =====================================================
# STUDENT RESUME PAGE - EXTRA ENDPOINTS
# (Resume Management: versions, single-resume detail /
#  delete, download, AI analyse)
# Added additively for the /student/resume/... routes
# used by the student Resume Management page.
# =====================================================


class StudentResumeVersionsView(APIView):
    """
    GET /student/resume/versions/

    Returns every resume the student has ever uploaded
    (newest first) so the Resume Management page can show
    a full version history, not just the active resume.
    """

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        resumes = Resume.objects.filter(
            student=request.user
        ).order_by(
            "-uploaded_at"
        )

        serializer = ResumeSerializer(
            resumes,
            many=True,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data
        )


class StudentResumeDetailView(APIView):
    """
    GET    /student/resume/<id>/      -> one resume's details
    DELETE /student/resume/<id>/      -> delete that resume version
    """

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request, id):

        resume = get_object_or_404(
            Resume,
            id=id,
            student=request.user
        )

        serializer = ResumeSerializer(
            resume,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data
        )

    def delete(self, request, id):

        resume = get_object_or_404(
            Resume,
            id=id,
            student=request.user
        )

        was_active = resume.is_active

        # remove the physical file from storage
        resume.delete_file()

        resume.delete()

        # if the deleted resume was the active one,
        # promote the next most recent version (if any)
        if was_active:

            next_resume = Resume.objects.filter(
                student=request.user
            ).order_by(
                "-uploaded_at"
            ).first()

            if next_resume:

                next_resume.is_active = True
                next_resume.save()

        return Response(
            {
                "message":
                "Resume deleted successfully"
            }
        )


class StudentResumeDownloadView(APIView):
    """
    GET /student/resume/<id>/download/

    Streams the resume file back as an attachment so it
    can be downloaded directly (in addition to resume_url
    which already links straight to the stored file).
    """

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request, id):

        resume = get_object_or_404(
            Resume,
            id=id,
            student=request.user
        )

        return FileResponse(
            resume.file.open("rb"),
            as_attachment=True,
            filename=resume.filename or resume.file.name
        )


class StudentResumeAnalyseView(APIView):
    """
    POST /student/resume/<id>/analyse/

    Re-runs the AI resume analysis (Groq) for a specific
    resume and saves the fresh results: skills, experience,
    education, certifications, projects, missing information,
    suggested job categories and the completeness score.
    """

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request, id):

        resume = get_object_or_404(
            Resume,
            id=id,
            student=request.user
        )

        try:

            # analyze_resume() takes the resume's Django file
            # object, not a filesystem path - resume.file.path
            # raises NotImplementedError under Cloudinary
            # storage, which is what was breaking this endpoint
            # ("Unable to analyse resume" in the UI).

            result = analyze_resume(
                resume.file
            )

        except Exception as e:

            return Response(
                {
                    "error":
                    "AI analysis failed",
                    "detail": str(e)
                },
                status=500
            )

        resume.resume_score = result.get(
            "resume_score", 0
        )

        resume.skills = result.get(
            "skills", []
        )

        resume.experience = result.get(
            "experience", []
        )

        resume.education = result.get(
            "education", []
        )

        resume.certifications = result.get(
            "certifications", []
        )

        resume.projects = result.get(
            "projects", []
        )

        resume.missing_information = result.get(
            "missing_information", []
        )

        resume.job_categories = result.get(
            "job_categories", []
        )

        resume.extracted_text = result.get(
            "text", ""
        )

        resume.save()

        serializer = ResumeSerializer(
            resume,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data
        )
