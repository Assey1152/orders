from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task


@shared_task()
def send_mail_task(subject: str, message: str, recipient_list: list):
    """Задача отправки электронного письма."""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=False,
    )
