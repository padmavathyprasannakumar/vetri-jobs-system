from django.apps import AppConfig



class JobsystemConfig(AppConfig):


    default_auto_field = "django.db.models.BigAutoField"


    name = "jobsystem"


    verbose_name = "Vetri Jobs System"



    def ready(self):

        """
        Application startup configuration.

        Used later for:
        - Signals
        - WhatsApp notification triggers
        - Email notifications
        - Auto profile creation
        """

        pass