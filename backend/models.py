from django.db import models
import uuid
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.validators import UnicodeUsernameValidator
from .tasks import generate_thumbnails_async

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

# Create your models here.


class UserManager(BaseUserManager):

    use_in_migrations = True

    def _create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError('Данный адрес электронной почты должен быть установлен')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Создает и возвращает `User` с адресом электронной почты,
        именем пользователя и паролем.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
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

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    objects = UserManager()
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
    avatar = models.ImageField(verbose_name='Аватар', upload_to='avatars/', null=True, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.email}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.avatar:
            generate_thumbnails_async.delay(self.id, self.__class__.__name__, 'avatar')


class Contact(models.Model):
    objects = models.Manager()
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

    def __str__(self):
        return f'{self.city} {self.street} {self.phone}'


class EmailVerificationToken(models.Model):
    objects = models.Manager()
    user = models.ForeignKey(User, related_name='user_confirm_token', on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Токен верификации почты'
        verbose_name_plural = 'Токены верификации почты'

    def __str__(self):
        return f"{self.user.email} {self.token}"

    def is_expired(self):
        return timezone.now() > self.expires_at


class Shop(models.Model):
    objects = models.Manager()
    name = models.CharField(max_length=60, unique=True, verbose_name='Название')
    url = models.URLField(null=True, blank=True, unique=True)
    user = models.OneToOneField(User, verbose_name='Продавец', on_delete=models.CASCADE, blank=True, null=True)
    state = models.BooleanField(verbose_name="Активен", default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Список магазинов'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    objects = models.Manager()
    name = models.CharField(max_length=60, unique=True, verbose_name='Название')
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', related_name='categories')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    objects = models.Manager()
    name = models.CharField(max_length=60, verbose_name='Название')
    category = models.ForeignKey(Category, verbose_name='Категория',
                                 on_delete=models.CASCADE,
                                 related_name='products',
                                 blank=True)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    objects = models.Manager()
    product = models.ForeignKey(Product, verbose_name='Продукт', on_delete=models.CASCADE, related_name='product_info')
    shop = models.ForeignKey(Shop, verbose_name='Магазин', on_delete=models.CASCADE, related_name='product_info')

    model = models.CharField(max_length=80, verbose_name='Модель', blank=True)
    ext_id = models.PositiveIntegerField(verbose_name='Артикул')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Розничная цена')
    image = models.ImageField(verbose_name='Изображение товара', upload_to='product_images/', null=True, blank=True)

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информация о продуктах'
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'ext_id'], name='unique_product_info'),
        ]

    def __str__(self):
        return f'{self.product.name} {self.model}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.image:
            generate_thumbnails_async.delay(self.id, self.__class__.__name__, 'image')


class Parameter(models.Model):
    objects = models.Manager()
    name = models.CharField(max_length=60, verbose_name='Название', unique=True)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    objects = models.Manager()
    product_info = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте',
                                     on_delete=models.CASCADE,
                                     related_name='product_parameter')
    parameter = models.ForeignKey(Parameter, verbose_name='Параметр',
                                  on_delete=models.CASCADE,
                                  related_name='product_parameter')

    value = models.CharField(verbose_name='Значение', max_length=60)

    class Meta:
        verbose_name = 'Параметр продукта'
        verbose_name_plural = 'Параметры продукта'
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'], name='unique_product_parameter'),
        ]

    def __str__(self):
        return f"{self.parameter.name} {self.value}"


class Order(models.Model):
    objects = models.Manager()
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
        ordering = ('-created_at',)

    def __str__(self):
        return self.state


class OrderItem(models.Model):
    objects = models.Manager()
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
