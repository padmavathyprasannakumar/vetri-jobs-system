import sib_api_v3_sdk
from django.conf import settings


def send_email(to_email, subject, message):

    configuration = sib_api_v3_sdk.Configuration()

    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        sender={
            "name": settings.BREVO_SENDER_NAME,
            "email": settings.BREVO_SENDER_EMAIL
        },
        to=[
            {
                "email": to_email
            }
        ],
        subject=subject,
        html_content=message
    )

    try:
        response = api_instance.send_transac_email(email)
        return response

    except Exception as e:
        print("BREVO EMAIL ERROR:", e)
        return None
