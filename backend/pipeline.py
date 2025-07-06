from social_core.exceptions import AuthAlreadyAssociated
from backend.models import User


def associate_by_email(backend, details, user=None, *args, **kwargs):
    """
    Если email из соцсети совпадает с существующим — логинимся как этот пользователь
    """
    if user:
        return {'user': user}

    email = details.get('email')
    if email:
        try:
            return {'user': User.objects.get(email=email)}
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            raise AuthAlreadyAssociated(backend)
