from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django.contrib.auth.password_validation import validate_password
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from backend.serializers import UserSerializer, LoginSerializer, ContactSerializer, ShopSerializer, \
    CategorySerializer, ProductInfoSerializer, OrderSerializer, OrderedItemsSerializer
from rest_framework import status
from .models import EmailVerificationToken, Contact, Shop, Product, Category, ProductInfo, Parameter, \
    ProductParameter, User, Order, OrderItem
from rest_framework.permissions import IsAuthenticated
from distutils.util import strtobool
from django.db.models import Q, Sum, F
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from requests import get
import yaml
from .permissions import IsVendor
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
from backend.tasks import send_mail_task
from django_rest_passwordreset.serializers import EmailSerializer
from django_rest_passwordreset.models import ResetPasswordToken, clear_expired, get_password_reset_token_expiry_time
from drf_spectacular.utils import extend_schema, OpenApiParameter
from social_core.backends.github import GithubOAuth2
from social_django.strategy import DjangoStrategy
from social_django.models import DjangoStorage

# Create your views here.


class GithubLoginView(APIView):

    @extend_schema(
        summary="Авторизация через GitHub",
        description="Принимает `access_token`, полученный от GitHub, и выполняет вход пользователя. "
                    "Если пользователь успешно авторизован — возвращается токен.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'access_token': {
                        'type': 'string',
                        'description': 'Токен, полученный после аутентификации через GitHub',
                        'example': '1234'
                    }
                },
                'required': ['access_token']
            }
        },
        responses={
            200: {
                'description': 'Успешная авторизация',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Token': {'type': 'string'}
                }
            },
            400: {
                'description': 'Ошибка авторизации',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Errors': {'type': 'string'}
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request, *args, **kwargs):
        access_token = request.data.get('access_token')

        strategy = DjangoStrategy(request=request, storage=DjangoStorage)
        backend = GithubOAuth2(strategy=strategy)
        user = backend.do_auth(access_token)

        if not user:
            return Response({'Status': False, 'Errors': 'Ошибка авторизации'}, status=status.HTTP_400_BAD_REQUEST)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'Status': True, 'Token': token.key}, status=status.HTTP_200_OK)


class UserRegisterView(APIView):
    """
        Класс для регистрации пользователя
    """

    @extend_schema(
        summary="Регистрация нового пользователя",
        description="Создаёт нового пользователя с обязательными полями: имя, фамилия, email, пароль, компания, должность. "
                    "После регистрации отправляется токен подтверждения на email.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'first_name': {'type': 'string', 'example': 'Иван'},
                    'last_name': {'type': 'string', 'example': 'Иванов'},
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': 'StrongPassword123!', 'format': 'password'},
                    'company': {'type': 'string', 'example': 'ООО Компания'},
                    'position': {'type': 'string', 'example': 'Менеджер'}
                },
                'required': ['first_name', 'last_name', 'email', 'password', 'company', 'position']
            }
        },
        responses={
            200: {
                'description': 'Пользователь успешно зарегистрирован',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'}
                }
            },
            400: {
                'description': 'Ошибка валидации или недостающие данные',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Errors': {'type': 'object'}
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return Response({'Status': False,
                                 'Errors': {'password': error_array}},
                                status=status.HTTP_400_BAD_REQUEST)

            user_serializer = UserSerializer(data=request.data)
            if user_serializer.is_valid():
                user = user_serializer.save()
                user.set_password(request.data['password'])
                user.save()

                token_obj = EmailVerificationToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=24)
                )
                send_mail_task.delay(
                    subject="Подтвердите ваш email",
                    message=f"Токен для подтверждения: {token_obj.token}",
                    recipient_list=[user.email]
                )

                return Response({'Status': True}, status=status.HTTP_200_OK)
            else:
                return Response({'Status': False,
                                 'Errors': user_serializer.errors},
                                status=status.HTTP_400_BAD_REQUEST)

        return Response({'Status': False,
                         'Errors': 'Не указаны все необходимые аргументы'},
                        status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    """
        Класс для входа пользователя
    """

    @extend_schema(
        summary="Авторизация пользователя",
        description="Выполняет вход пользователя по email и паролю. "
                    "Возвращает токен авторизации, если данные корректны.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': 'password123', 'format': 'password'}
                },
                'required': ['email', 'password']
            }
        },
        responses={
            200: {
                'description': 'Успешный вход',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Token': {'type': 'string'}
                }
            },
            400: {
                'description': 'Ошибка авторизации',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Errors': {'type': 'string'}
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token, created = Token.objects.get_or_create(user=user)
            return Response({'Status': True, 'Token': token.key}, status=status.HTTP_200_OK)
        return Response({'Status': False, 'Errors': 'Ошибка авторизации'}, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    """
    Класс для верификации почты пользователя
    """

    @extend_schema(
        summary="Подтверждение email по токену",
        description="Подтверждает email пользователя с помощью одноразового токена. "
                    "Если токен и email совпадают и не истек — аккаунт активируется.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'token': {'type': 'string', 'example': 'abc123xyz789'}
                },
                'required': ['email', 'token']
            }
        },
        responses={
            200: {
                'description': 'Email успешно подтверждён',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            400: {
                'description': 'Ошибка подтверждения',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'error': {'type': 'string'},
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):
        if {'email', 'token'}.issubset(request.data):

            verification_token = EmailVerificationToken.objects.filter(token=request.data['token'],
                                                                       user__email=request.data['email']).first()

            if verification_token:
                if verification_token.is_expired():
                    return Response({'Status': False, 'error': 'Токен истек'}, status=status.HTTP_400_BAD_REQUEST)
                user = verification_token.user
                user.is_active = True
                user.save()
                verification_token.delete()  # Можно удалить после использования
                return Response({'Status': True, 'message': 'Email успешно подтвержден'}, status=status.HTTP_200_OK)
        return Response({'Status': False, 'error': 'Неверный email или токен'}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordRequestView(APIView):
    """
    Класс для управления сбросом пароля пользователя с отправкой почты с помощью Celery
    """

    @extend_schema(
        summary="Запрос на сброс пароля",
        description="Отправляет токен для сброса пароля на указанный email. "
                    "Если у пользователя уже есть активный токен — будет использован он. "
                    "Иначе создаётся новый.",
        request=EmailSerializer,
        responses={
            200: {
                'description': 'Токен успешно отправлен',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'}
                }
            },
            400: {
                'description': 'Ошибка запроса',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'error': {'type': 'string'},
                    'Errors': {'type': 'object'}
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data['email']

            # Удалим все истекшие токены
            password_reset_token_validation_time = get_password_reset_token_expiry_time()
            now_minus_expiry_time = timezone.now() - timedelta(hours=password_reset_token_validation_time)
            clear_expired(now_minus_expiry_time)

            user = User.objects.filter(email=email).first()

            if not user or not user.is_active:
                return Response({'Status': False, 'error': 'Пользователь не найден'}, status=status.HTTP_400_BAD_REQUEST)

            password_reset_tokens = user.password_reset_tokens.all()

            # проверка, существует ли токен для пользователя
            if password_reset_tokens.count():
                # если существует хотя бы один, используем его
                token = password_reset_tokens.first()
            # если не существует, создаем новый
            else:
                token = ResetPasswordToken.objects.create(user=user)
            if token:
                # Направляем токен на почту
                send_mail_task.delay(
                    subject="Сброс пароля",
                    message=f"Токен для сброса пароля: {token.key}",
                    recipient_list=[token.user.email]
                )

            return Response({'Status': True}, status=status.HTTP_200_OK)
        return Response({'Status': False,
                         'Errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    """
    Класс для управления профилем пользователя
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Получить данные текущего пользователя",
        description="Возвращает данные авторизованного пользователя (имя, email, телефон и т.д.).",
        responses={200: UserSerializer},
        tags=["Пользователь"]
    )
    def get(self, request):
        user_serializer = UserSerializer(request.user)
        return Response(user_serializer.data)

    @extend_schema(
        summary="Обновить данные текущего пользователя",
        description="Позволяет обновить данные текущего пользователя, включая пароль. "
                    "Если передан новый пароль — он проверяется на соответствие политике безопасности.",
        request=UserSerializer,
        responses={
            200: {
                'description': 'Данные успешно обновлены',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'}
                }
            },
            400: {
                'description': 'Ошибка валидации данных или пароля',
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Errors': {'type': 'string'},
                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):

        if 'password' in request.data:
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return Response({'Status': False,
                                 'Errors': {'password': error_array}},
                                status=status.HTTP_400_BAD_REQUEST)

        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user = user_serializer.save()
            if 'password' in request.data:
                user.set_password(request.data['password'])
            user.save()
            return Response({'Status': True}, status=status.HTTP_200_OK)
        else:
            return Response({'Status': False,
                             'Errors': user_serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)


class ContactView(APIView):
    """
    Класс для управления контактами
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Получить список контактов пользователя",
        description="Возвращает все сохранённые контакты текущего авторизованного пользователя.",
        responses={200: ContactSerializer(many=True)},
        tags=["Пользователь"]
    )
    def get(self, request):
        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Добавить новый контакт",
        description="Создаёт новый контакт для текущего пользователя. ",
        request=ContactSerializer,
        responses={
            201: {
                'description': 'Контакт успешно создан',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'id': {'type': 'integer'},
                        'city': {'type': 'string'},
                        'street': {'type': 'string'},
                        'house': {'type': 'string'},
                        'apartment': {'type': 'string'},
                        'phone': {'type': 'string'}

                }
            },
            400: {
                'description': 'Ошибка валидации данных',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean', 'example': 'False'},
                        'Errors': {'type': 'object'}

                }
            }
        },
        tags=["Пользователь"]
    )
    def post(self, request):
        data = {**request.data, 'user': request.user.id}
        serializer = ContactSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True, **serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Обновить существующий контакт",
        description="Изменяет данные контакта по его ID. ",
        request=ContactSerializer,
        responses={
            200: {
                'description': 'Контакт успешно обновлён',
                'type': 'object',
                'properties': {'Status': {'type': 'boolean'}}
            },
            400: {
                'description': 'Ошибка валидации или отсутствие аргументов',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'Errors': {'type': 'object'}
                }
            },
            404: {
                'description': 'Контакт не найден',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'Errors': {'type': 'string'}
                }
            }
        },
        tags=["Пользователь"]
    )
    def put(self, request):
        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(user_id=request.user.id, id=request.data['id']).first()
                if not contact:
                    return Response({'Status': False, 'Errors': 'Контакт не найден'}, status=status.HTTP_404_NOT_FOUND)
                serializer = ContactSerializer(contact, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response({'Status': True}, status=status.HTTP_200_OK)
                return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Удалить один или несколько контактов",
        description="Удаляет контакты по списку ID (передаются через запятую в параметре `items`).",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'items': {
                        'type': 'string',
                        'description': 'Список ID контактов для удаления (через запятую)',
                        'example': '1,2,3'
                    }
                },
                'required': ['items']
            }
        },
        responses={
            200: {
                'description': 'Контакты успешно удалены',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'detail': {'type': 'string'}
                }
            },
            400: {
                'description': 'Недостаточно аргументов',
                'type': 'object',
                'properties': {
                        'Status': {'type': 'boolean'},
                        'Errors': {'type': 'string'}

                }
            }
        },
        tags=["Пользователь"]
    )
    def delete(self, request):
        items = request.data.get('items')
        if items:
            id_list = items.split(',')
            query = Q()
            contact_found = False
            for contact_id in id_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    contact_found = True
            if contact_found:
                deleted_count = Contact.objects.filter(query).delete()[0]
                print(deleted_count)
                return Response({'Status': True, 'detail': f'Контактов удалено: {deleted_count}'},
                                status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Получить список всех категорий",
    description="Возвращает список всех доступных категорий товаров.",
    responses={200: CategorySerializer(many=True)},
    tags=["Категории"]
)
class CategoriesView(ListAPIView):
    """
    Класс для просмотра списка категорий
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


@extend_schema(
    summary="Получить список активных магазинов",
    description="Возвращает список всех магазинов, у которых состояние (state) установлено как 'активен'.",
    responses={200: ShopSerializer(many=True)},
    tags=["Магазины"]
)
class ShopsView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Класс для просмотра товаров
    """

    @extend_schema(
        summary="Получить информацию о товарах",
        description="Возвращает список товаров с фильтрацией по магазину и категории. "
                    "Можно указать параметры запроса `shop_id` и/или `category_id`.",
        parameters=[
            OpenApiParameter(name='shop_id', type=int, location='query',
                             description='Фильтр по ID магазина'),
            OpenApiParameter(name='category_id', type=int, location='query',
                             description='Фильтр по ID категории товара'),
        ],
        responses=ProductInfoSerializer(many=True),
        tags=["Информация о товарах"]
    )
    def get(self, request):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(product__category_id=category_id)
        queryset = ProductInfo.objects.filter(query).select_related('shop', 'product__category').prefetch_related(
            'product_parameter__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class PartnerState(APIView):
    """
    Класс для управления состоянием продавца
    """

    permission_classes = (IsAuthenticated, IsVendor)

    @extend_schema(
        summary="Получить текущее состояние магазина",
        responses={
            200: ShopSerializer,
            404: {'description': 'Магазин не найден'}},
        tags=["Партнер"],
    )
    def get(self, request):
        """
            Возвращает текущее состояние (включен/выключен) магазина продавца.
        """
        try:
            shop = request.user.shop
        except User.shop.RelatedObjectDoesNotExist:
            return Response({'Status': False, 'Errors': 'Магазин отсутствует'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    @extend_schema(
        summary="Обновить состояние магазина",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'state': {'type': 'string', 'example': 'True',
                              'description': 'Значение должно быть строкой "True" или "False"'}
                },
                'required': ['state']
            }
        },

        responses={
            200: {'description': 'Статус обновлен успешно'},
            400: {'description': 'Ошибка валидации или недостаточно данных'},
        },
        tags=["Партнер"]
    )
    def post(self, request):
        """
            Изменяет состояние магазина продавца (вкл/выкл). Статус передается в параметре `state` как строка 'True' или 'False'.
        """
        new_state = request.data.get('state')
        if new_state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(new_state))
                return JsonResponse({'Status': True}, status=status.HTTP_200_OK)
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)


class PartnerUpdate(APIView):
    """
        Класс для обновления прайса продавца
    """
    permission_classes = (IsAuthenticated, IsVendor)

    @extend_schema(
        summary="Обновление прайса продавца по внешней ссылке",
        description="Принимает URL-адрес и проверяет его корректность. "
                    "Если URL валиден, происходит попытка загрузки данных (например, файла или JSON).",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'example': 'https://example.com/data.yaml ',
                        'description': 'URL, откуда будут загружаться данные'
                    }
                },
                'required': ['url']
            }
        },
        responses={
            200: {'description': 'Данные успешно загружены'},
            400: {'description': 'Ошибка: неверный URL или недостаточно данных'},
        },
        tags=["Партнер"]
    )
    def post(self, request):
        url = request.data.get('url')
        if url:
            validator = URLValidator()
            try:
                validator(url)
            except ValidationError as e:
                return Response({'Status': False, 'Errors': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            stream = get(url)
            data = yaml.safe_load(stream.content)
            shop, created = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
            for category in data['categories']:
                new_category, created = Category.objects.get_or_create(id=category['id'], name=category['name'])
                new_category.shops.add(shop.id)
                new_category.save()
            ProductInfo.objects.filter(shop_id=shop.id).delete()
            for item in data['goods']:
                product, created = Product.objects.get_or_create(category_id=item['category'], name=item['name'])
                product_info = ProductInfo.objects.create(product_id=product.id,
                                                          shop_id=shop.id,
                                                          model=item['model'],
                                                          ext_id=item['id'],
                                                          quantity=item['quantity'],
                                                          price=item['price'],
                                                          price_rrc=item['price_rrc'])
                for name, value in item['parameters'].items():
                    parameter, created = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.create(parameter_id=parameter.id,
                                                    product_info_id=product_info.id,
                                                    value=value)
            return JsonResponse({'Status': True}, status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)


class PartnerOrders(APIView):
    """
    Класс для вывода списка заказов продавца
    """
    permission_classes = (IsAuthenticated, IsVendor)

    @extend_schema(
        summary="Получить список заказов продавца",
        description="Возвращает список всех заказов, в которых есть товары, принадлежащие магазинам текущего пользователя."
                    "Включает общую сумму заказа и детали товаров.",
        responses={200: OrderSerializer(many=True)},
        tags=["Партнер"]
    )
    def get(self, request):
        orders = Order.objects.filter(order_items__product_info__shop__user_id=request.user.id).exclude(
            state='basket').prefetch_related(
            'order_items__product_info__product__category',
            'order_items__product_info__product_parameter__parameter',
        ).annotate(
            total_sum=Sum(F('order_items__product_info__price') * F('order_items__quantity'))
        ).distinct()
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    """
        Класс для управления корзиной
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Получить содержимое корзины",
        description="Возвращает текущее состояние корзины пользователя (только один заказ со статусом 'basket'). "
                    "Включает информацию о товарах, категориях и общей стоимости.",
        responses={200: OrderSerializer(many=True)},
        tags=["Корзина"]
    )
    def get(self, request):
        basket = Order.objects.filter(user_id=request.user.id, state='basket').prefetch_related(
            'order_items__product_info__product__category',
            'order_items__product_info__product_parameter__parameter',
        ).annotate(
            total_sum=Sum(F('order_items__product_info__price') * F('order_items__quantity'))
        ).distinct()
        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Добавить товар(ы) в корзину",
        description="Добавляет один или несколько товаров в корзину пользователя. "
                    "Если корзины нет — создаётся новая.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'items': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'product_info': {'type': 'integer', 'example': 1},
                                'quantity': {'type': 'integer', 'example': 2}
                            },
                            'required': ['product_info', 'quantity']
                        }
                    }
                },
                'required': ['items']
            }
        },
        responses={
            200: {'description': 'Товар(ы) успешно добавлены'},
            400: {'description': 'Ошибка валидации или неверный формат данных'}
        },
        tags=["Корзина"]
    )
    def post(self, request):

        items_data = request.data.get('items', [])
        if not isinstance(items_data, list):
            return Response({'Status': False, 'Errors': 'Неправильный формат запроса'},
                            status=status.HTTP_400_BAD_REQUEST)

        if items_data:
            added_items = 0
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            for item in items_data:
                item['order'] = basket.id
                serializer = OrderedItemsSerializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    added_items += 1
                else:
                    return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'Status': True, 'detail': f'Товаров добавлено: {added_items}'}, status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Удалить товары из корзины",
        description="Удаляет товары из корзины по их ID. "
                    "ID передаются в виде строки, разделённой запятыми, например: `1,2,3`.",
        parameters=[
            OpenApiParameter(
                name='items',
                type=str,
                location='body',
                description='Список ID товаров в корзине, которые нужно удалить'
            )
        ],
        responses={
            200: {'description': 'Товар(ы) успешно удалены'},
            400: {'description': 'Неверный формат данных или отсутствуют аргументы'}
        },
        tags=["Корзина"]
    )
    def delete(self, request):
        items_data = request.data.get('items')

        if items_data:
            id_list = items_data.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            items_found = False
            for item_id in id_list:
                if item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=item_id)
                    items_found = True
            if items_found:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return Response({'Status': True, 'detail': f'Товаров удалено: {deleted_count}'},
                                status=status.HTTP_200_OK)
        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Обновить количество товаров в корзине",
        description="Изменяет количество определённых товаров в корзине. "
                    "Ожидает список объектов с полями `id` и `quantity`.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'items': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 1},
                                'quantity': {'type': 'integer', 'example': 5}
                            },
                            'required': ['id', 'quantity']
                        }
                    }
                },
                'required': ['items']
            }
        },
        responses={
            200: {'description': 'Товар(ы) успешно обновлены'},
            400: {'description': 'Ошибка валидации или неверный формат данных'}
        },
        tags=["Корзина"]
    )
    def put(self, request):
        items_data = request.data.get('items', [])
        if not isinstance(items_data, list):
            return Response({'Status': False, 'Errors': 'Неправильный формат запроса'},
                            status=status.HTTP_400_BAD_REQUEST)
        if items_data:
            updated_items = 0
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            for item in items_data:
                if type(item['id']) == int and type(item['quantity']) == int and item['quantity'] > 0:
                    updated_items += OrderItem.objects.filter(order_id=basket.id, id=item['id']).update(
                        quantity=item['quantity'])
            return Response({'Status': True, 'detail': f'Товаров обновлено: {updated_items}'},
                            status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)


class OrderView(APIView):
    """
    Класс для управления заказами
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Получить список заказов пользователя",
        description="Возвращает список всех оформленных заказов пользователя (кроме корзины). "
                    "Включает информацию о товарах, категориях и общей сумме заказа.",
        responses={200: OrderSerializer(many=True)},
        tags=["Заказы"]
    )
    def get(self, request):
        basket = Order.objects.filter(user_id=request.user.id).exclude(state='basket').prefetch_related(
            'order_items__product_info__product__category',
            'order_items__product_info__product_parameter__parameter',
        ).annotate(
            total_sum=Sum(F('order_items__product_info__price') * F('order_items__quantity'))
        ).distinct()
        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Подтвердить заказ и отправить уведомление",
        description="Обновляет состояние указанного заказа на 'new' и отправляет email-уведомление пользователю. "
                    "Требует ID заказа и контактной информации.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'example': '1', 'description': 'ID заказа'},
                    'contact': {'type': 'string', 'example': '2', 'description': 'ID контактной информации'}
                },
                'required': ['id', 'contact']
            }
        },
        responses={
            200: {'description': 'Заказ успешно подтверждён'},
            400: {'description': 'Ошибка валидации или отсутствуют аргументы'}
        },
        tags=["Заказы"]
    )
    def post(self, request):
        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():

                try:
                    is_updated = Order.objects.filter(user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new'
                    )
                except IntegrityError as e:
                    print(e)
                    return Response({'Status': False, 'Errors': 'Ошибка'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    if is_updated:
                        order = Order.objects.get(user_id=request.user.id, id=request.data['id'])
                        send_mail_task.delay(
                            subject="Изменение статуса заказа",
                            message=f"Статус заказа {order.id} изменён на {order.state}",
                            recipient_list=[request.user.email]
                        )

                        return Response({'Status': True, 'detail': f'Заказ создан'},
                                        status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)
