from rest_framework.permissions import BasePermission



# =====================================================
# AUTHENTICATED USER
# =====================================================


class IsAuthenticatedUser(BasePermission):

    """
    Any logged-in user
    """


    def has_permission(self, request, view):

        return bool(

            request.user

            and

            request.user.is_authenticated

        )






# =====================================================
# ROLE BASE PERMISSION
# =====================================================


class RolePermission(BasePermission):


    allowed_roles = []



    def has_permission(self, request, view):


        if not request.user.is_authenticated:

            return False



        return request.user.role in self.allowed_roles







# =====================================================
# STUDENT
# =====================================================


class IsStudent(RolePermission):


    """
    Student permissions:

    - Profile
    - Education
    - Skills
    - Resume
    - Jobs
    - Applications
    - Interviews
    - Chatbot

    """


    allowed_roles = [

        "student"

    ]








# =====================================================
# COMPANY / RECRUITER
# =====================================================


class IsCompany(RolePermission):


    """
    Company permissions:

    - Company profile
    - Create jobs
    - Manage jobs
    - Candidates
    - Interviews

    """


    allowed_roles = [

        "company"

    ]









# =====================================================
# PLACEMENT ADMIN
# =====================================================


class IsPlacementAdmin(RolePermission):


    """
    Placement permissions:

    - Students
    - Companies
    - Placement drives
    - Reports
    - Notifications

    """


    allowed_roles = [

        "placement_admin"

    ]









# =====================================================
# SUPER ADMIN
# =====================================================


class IsSuperAdmin(RolePermission):


    """
    Complete platform access

    """


    allowed_roles = [

        "super_admin"

    ]









# =====================================================
# ADMIN ACCESS
# =====================================================


class IsAdmin(BasePermission):


    """
    Placement Admin + Super Admin
    """


    def has_permission(self,request,view):


        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# ADMIN ONLY
# =====================================================


class SuperAdminOnly(BasePermission):


    """
    Only Super Admin
    """


    def has_permission(self,request,view):


        return (

            request.user.is_authenticated

            and

            request.user.role ==

            "super_admin"

        )









# =====================================================
# COMPANY OR ADMIN
# =====================================================


class IsCompanyOrAdmin(BasePermission):


    """
    Company + Placement Admin + Super Admin

    Used:

    - Jobs
    - Candidates
    - Interviews

    """


    def has_permission(self,request,view):


        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "company",

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# STUDENT OR ADMIN
# =====================================================


class IsStudentOrAdmin(BasePermission):


    """
    Student own data
    Admin management
    """


    def has_permission(self,request,view):


        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "student",

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# OBJECT OWNER CHECK
# =====================================================


class IsOwner(BasePermission):


    """
    Object ownership checking

    Supports:

    Student Profile
    Company Profile
    Job
    Application

    """



    def has_object_permission(

        self,

        request,

        view,

        obj

    ):


        if request.user.role == "super_admin":

            return True





        # Profile owner


        if hasattr(obj,"user"):


            return (

                obj.user == request.user

            )






        # Company job owner


        if hasattr(obj,"company"):


            return (

                obj.company.user

                ==

                request.user

            )






        # Application owner


        if hasattr(obj,"student"):


            return (

                obj.student.user

                ==

                request.user

            )




        return False










# =====================================================
# OWNER OR ADMIN
# =====================================================


class IsOwnerOrAdmin(BasePermission):


    """

    Owner can modify own data

    Admin can manage everything

    """



    def has_object_permission(

        self,

        request,

        view,

        obj

    ):



        if request.user.role in [

            "placement_admin",

            "super_admin"

        ]:


            return True





        if hasattr(obj,"user"):


            return obj.user == request.user






        if hasattr(obj,"company"):


            return (

                obj.company.user

                ==

                request.user

            )






        if hasattr(obj,"student"):


            return (

                obj.student.user

                ==

                request.user

            )



        return False











# =====================================================
# STUDENT APPLICATION OWNER
# =====================================================


class IsStudentApplicationOwner(BasePermission):


    """
    Student can access only own applications

    Admin can view all

    """



    def has_object_permission(

        self,

        request,

        view,

        obj

    ):



        if request.user.role in [

            "placement_admin",

            "super_admin"

        ]:


            return True




        return (

            obj.student.user

            ==

            request.user

        )









# =====================================================
# COMPANY JOB OWNER
# =====================================================


class IsCompanyJobOwner(BasePermission):


    """

    Company can manage only own jobs

    """


    def has_object_permission(

        self,

        request,

        view,

        obj

    ):



        if request.user.role in [

            "placement_admin",

            "super_admin"

        ]:


            return True





        return (

            obj.company.user

            ==

            request.user

        )









# =====================================================
# COMPANY CANDIDATE ACCESS
# =====================================================


class CanManageCandidates(BasePermission):


    """

    Recruiter can only see

    candidates applying

    to their company jobs

    """



    def has_permission(

        self,

        request,

        view

    ):



        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "company",

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# INTERVIEW ACCESS
# =====================================================


class CanManageInterview(BasePermission):


    """

    Student:

        View own interview


    Company:

        Create/manage interviews


    Admin:

        Full access

    """



    def has_permission(

        self,

        request,

        view

    ):



        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "student",

            "company",

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# CHATBOT ACCESS
# =====================================================


class CanUseChatbot(BasePermission):


    """

    All authenticated users

    can use AI assistant

    """



    def has_permission(

        self,

        request,

        view

    ):



        return bool(

            request.user

            and

            request.user.is_authenticated

        )









# =====================================================
# WHATSAPP MANAGEMENT
# =====================================================


class CanManageWhatsApp(BasePermission):


    """

    WhatsApp configuration

    Super Admin only

    """



    def has_permission(

        self,

        request,

        view

    ):



        if not request.user.is_authenticated:

            return False



        return request.user.role == "super_admin"









# =====================================================
# CMS MANAGEMENT
# =====================================================


class CanManageCMS(BasePermission):


    """

    Website content management

    """



    def has_permission(

        self,

        request,

        view

    ):



        if not request.user.is_authenticated:

            return False



        return request.user.role == "super_admin"









# =====================================================
# NOTIFICATION MANAGEMENT
# =====================================================


class CanSendNotification(BasePermission):


    """

    Placement Admin

    Super Admin

    can send notifications

    """



    def has_permission(

        self,

        request,

        view

    ):



        if not request.user.is_authenticated:

            return False



        return request.user.role in [

            "placement_admin",

            "super_admin"

        ]









# =====================================================
# READ ONLY ACCESS
# =====================================================


class ReadOnly(BasePermission):


    """

    GET only

    """



    def has_permission(

        self,

        request,

        view

    ):



        return request.method in [

            "GET",

            "HEAD",

            "OPTIONS"

        ]









# =====================================================
# READ ONLY OR ADMIN
# =====================================================


class ReadOnlyOrAdmin(BasePermission):


    """

    Public read

    Admin write

    """



    def has_permission(

        self,

        request,

        view

    ):



        if request.method in [

            "GET",

            "HEAD",

            "OPTIONS"

        ]:


            return True




        return (

            request.user.is_authenticated

            and

            request.user.role in [

                "placement_admin",

                "super_admin"

            ]

        )