import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings


def send_email(to_email, subject, message):

    try:

        email = Mail(
            from_email=(
                settings.SENDGRID_SENDER_EMAIL
            ),
            to_emails=to_email,
            subject=subject,
            html_content=message
        )


        sg = SendGridAPIClient(
            settings.SENDGRID_API_KEY
        )


        response = sg.send(email)


        return response


    except Exception as e:

        print(
            "SENDGRID EMAIL ERROR:",
            e
        )

        return None
