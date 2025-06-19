from django.db import models
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import config
import uuid
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.validators import UnicodeUsernameValidator

STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),

)

engine = create_async_engine(config.PG_DSN)
Session = async_sessionmaker(bind=engine, expire_on_commit=False)


# Create your models here.

class User(AbstractUser):

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = []
    email = models.EmailField(_('email address'), unique=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _("username"),
        max_length=150,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)

    type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='buyer')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.username}'


class UserManager(BaseUserManager):

    use_in_migrations = True

    def _create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('Указанное имя пользователя должно быть установлено')

        if not email:
            raise ValueError('Данный адрес электронной почты должен быть установлен')

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Создает и возвращает `User` с адресом электронной почты,
        именем пользователя и паролем.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        """
        Создает и возвращает пользователя с правами
        суперпользователя (администратора).
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self._create_user(username, email, password, **extra_fields)


class Contact(models.Model):

    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.CASCADE, related_name='user_contact')

    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=50, verbose_name='Улица')
    house = models.CharField(max_length=50, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=50, verbose_name='Корпус', blank=True)
    building = models.CharField(max_length=50, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=50, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон')

    class Meta:
        verbose_name = 'Контакты пользователя'
        verbose_name_plural = 'Список контактов'


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, related_name='user_confirm_token', on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.user.email} - {self.token}"

    def is_expired(self):
        return timezone.now() > self.expires_at


class Shop(models.Model):

    name = models.CharField(max_length=60, unique=True, verbose_name='Название')
    url = models.URLField(null=True, blank=True, unique=True)
    user = models.OneToOneField(User, verbose_name='Продавец', on_delete=models.CASCADE)
    state = models.BooleanField(verbose_name="Активен", default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Список магазинов'

    def __str__(self):
        return self.name


class Category(models.Model):

    name = models.CharField(max_length=60, unique=True, verbose_name='Название')
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', related_name='categories')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class Product(models.Model):

    name = models.CharField(max_length=60, verbose_name='Название')
    category = models.ForeignKey(Category, verbose_name='Категория',
                                 on_delete=models.CASCADE,
                                 related_name='products',
                                 blank=True)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'

    def __str__(self):
        return self.name


class ProductInfo(models.Model):

    product = models.ForeignKey(Product, verbose_name='Продукт', on_delete=models.CASCADE, related_name='product_info')
    shop = models.ForeignKey(Shop, verbose_name='Магазин', on_delete=models.CASCADE, related_name='product_info')

    model = models.CharField(max_length=80, verbose_name='Модель', blank=True)
    ext_id = models.PositiveIntegerField(verbose_name='Артикул')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Розничная цена')

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информация о продуктах'


class Parameter(models.Model):

    name = models.CharField(max_length=60, verbose_name='Название', unique=True)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'

    def __str__(self):
        return self.name


class ProductParameter(models.Model):

    product_info = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте',
                                     on_delete=models.CASCADE,
                                     related_name='product_parameter')
    parameter = models.ForeignKey(Parameter, verbose_name='Параметр',
                                  on_delete=models.CASCADE,
                                  related_name='product_parameter')

    value = models.CharField(verbose_name='Значение', max_length=60)

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информация о продуктах'
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'], name='unique_product_parameter'),
        ]


class Order(models.Model):

    user = models.ForeignKey(User, verbose_name='Пользователь',
                             on_delete=models.CASCADE,
                             related_name='orders',
                             blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=15, verbose_name='Статус', choices=STATE_CHOICES)
    contact = models.ForeignKey(Contact, verbose_name='Контакты получателя',
                                on_delete=models.CASCADE,
                                blank=True,
                                null=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Список заказов'

    def __str__(self):
        return self.state


class OrderItem(models.Model):

    order = models.ForeignKey(Order,
                              verbose_name='Заказ',
                              on_delete=models.CASCADE,
                              related_name='order_items',
                              blank=True)

    product_info = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте',
                                     on_delete=models.CASCADE,
                                     related_name='product_orders',
                                     blank=True)

    quantity = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        constraints = [
                    models.UniqueConstraint(fields=['product_info', 'order_id'], name='unique_product_order'),
                ]
