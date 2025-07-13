from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task
from easy_thumbnails.files import generate_all_aliases
from django.apps import apps


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


@shared_task()
def generate_thumbnails_async(instance_id, model_name, field_name):
    """
    Задача генерации миниатюр для изображений модели
    :param instance_id:
    :param model_name:
    :param field_name:
    :return:
    """

    Model = apps.get_model(app_label='backend', model_name=model_name)
    try:
        instance = Model.objects.get(id=instance_id)
        field = getattr(instance, field_name)
        if field:
            generate_all_aliases(field, include_global=True)
    except Model.DoesNotExist:
        pass
