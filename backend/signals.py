from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from rest_framework.authtoken.models import Token
from .models import EmailVerificationToken, User, Order
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django_rest_passwordreset.signals import reset_password_token_created


update_order_state_signal = Signal()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_verification_token(sender, instance, created, **kwargs):
    if created:
        # Создаем токен
        token_obj = EmailVerificationToken.objects.create(
            user=instance,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        # Отправляем письмо
        send_mail(
            subject="Подтвердите ваш email",
            message=f"Токен для подтверждения: {token_obj.token}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=False,
        )


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    # Отправляем токен на email
    send_mail(
        subject="Сброс пароля",
        message=f"Токен для сброса пароля: {reset_password_token.key}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_password_token.user.email],
        fail_silently=False,
    )


@receiver(update_order_state_signal)
def update_order_state(user_id: int, order_id: int, **kwargs):

    user = User.objects.get(id=user_id)
    order = Order.objects.get(id=order_id)
    # Отправляем письмо пользователю
    send_mail(
        subject="Изменение статуса заказа",
        message=f"Статус заказа {order_id} изменён на {order.state}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )