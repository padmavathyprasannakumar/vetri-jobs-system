# =====================================================
# VETRI JOBS JWT AUTHENTICATION
# =====================================================


from rest_framework_simplejwt.authentication import (
    JWTAuthentication
)


from rest_framework.exceptions import (
    AuthenticationFailed
)


from django.contrib.auth import get_user_model



# Get custom user model

User = get_user_model()





# =====================================================
# CUSTOM JWT AUTHENTICATION
# =====================================================


class VetriJWTAuthentication(
    JWTAuthentication
):


    """
    Custom JWT Authentication


    Used by:


    Student

    Company / Recruiter

    Placement Administrator

    Super Admin



    React sends:


    Authorization:

    Bearer <access_token>


    """


    # =================================================
    # GET USER FROM TOKEN
    # =================================================


    def get_user(
        self,
        validated_token
    ):


        try:


            # JWT contains user_id

            user_id = validated_token.get(
                "user_id"
            )



            if not user_id:


                raise AuthenticationFailed(

                    "Token does not contain user id",

                    code="invalid_token"

                )



            user = User.objects.get(

                id=user_id

            )



        except User.DoesNotExist:


            raise AuthenticationFailed(

                "User account not found",

                code="user_not_found"

            )



        except Exception:


            raise AuthenticationFailed(

                "Invalid authentication token",

                code="invalid_token"

            )





        # =================================================
        # ACCOUNT STATUS CHECK
        # =================================================


        if not user.is_active:


            raise AuthenticationFailed(

                "User account is disabled",

                code="inactive_user"

            )





        return user





# =====================================================
# OPTIONAL ROLE BASED AUTHENTICATION
# =====================================================


class StudentJWTAuthentication(
    VetriJWTAuthentication
):


    """
    Only Student accounts

    """


    def get_user(
        self,
        validated_token
    ):


        user = super().get_user(

            validated_token

        )


        if user.role != "student":


            raise AuthenticationFailed(

                "Student account required"

            )


        return user





# =====================================================
# COMPANY AUTHENTICATION
# =====================================================


class CompanyJWTAuthentication(
    VetriJWTAuthentication
):


    """
    Only Recruiter / Company accounts

    """


    def get_user(
        self,
        validated_token
    ):


        user = super().get_user(

            validated_token

        )


        if user.role != "company":


            raise AuthenticationFailed(

                "Company account required"

            )


        return user





# =====================================================
# PLACEMENT ADMIN AUTHENTICATION
# =====================================================


class PlacementAdminJWTAuthentication(
    VetriJWTAuthentication
):


    """
    Placement Department

    """


    def get_user(
        self,
        validated_token
    ):


        user = super().get_user(

            validated_token

        )


        if user.role not in [

            "placement_admin",

            "super_admin"

        ]:


            raise AuthenticationFailed(

                "Placement administrator access required"

            )


        return user





# =====================================================
# SUPER ADMIN AUTHENTICATION
# =====================================================


class SuperAdminJWTAuthentication(
    VetriJWTAuthentication
):


    """
    Django platform administrator

    """


    def get_user(
        self,
        validated_token
    ):


        user = super().get_user(

            validated_token

        )


        if user.role != "super_admin":


            raise AuthenticationFailed(

                "Super admin access required"

            )


        return user