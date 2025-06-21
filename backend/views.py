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
from .signals import update_order_state_signal
# Create your views here.


class UserRegisterView(APIView):
    """
        Класс для регистрации пользователя
    """

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

    def post(self, request):
        if {'email', 'token'}.issubset(request.data):

            verification_token = EmailVerificationToken.objects.filter(token=request.data['token'],
                                                                       user__email=request.data['email']).first()

            if verification_token:
                if verification_token.is_expired():
                    return Response({'error': 'Токен истек'}, status=status.HTTP_400_BAD_REQUEST)
                user = verification_token.user
                user.is_active = True
                user.save()
                verification_token.delete()  # Можно удалить после использования
                return Response({'Status': True, 'message': 'Email успешно подтвержден'}, status=status.HTTP_200_OK)
        return Response({'Status': False, 'error': 'Неверный email или токен'}, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    """
    Класс для управления профилем пользователя
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user_serializer = UserSerializer(request.user)
        return Response(user_serializer.data)

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

    def get(self, request):
        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = {**request.data, 'user': request.user.id}
        serializer = ContactSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True, **serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(user_id=request.user.id, id=request.data['id'])
                if not contact:
                    return Response({'Status': False, 'Errors': 'Контакт не найден'}, status=status.HTTP_404_NOT_FOUND)
                serializer = ContactSerializer(contact, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response({'Status': True}, status=status.HTTP_200_OK)
                return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)

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


class CategoriesView(ListAPIView):
    """
    Класс для просмотра списка категорий
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


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

    def get(self, request):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(category_id=category_id)
        queryset = ProductInfo.objects.filter(query).select_related('shop', 'product__category').prefetch_related(
            'product_parameter__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class PartnerState(APIView):
    """
    Класс для управления состоянием продавца
    """

    permission_classes = (IsAuthenticated, IsVendor)

    def get(self, request):
        try:
            shop = request.user.shop
        except User.shop.RelatedObjectDoesNotExist:
            return Response({'Status': False, 'Errors': 'Магазин отсутствует'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request):
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

    def get(self, request):
        basket = Order.objects.filter(user_id=request.user.id, state='basket').prefetch_related(
            'order_items__product_info__product__category',
            'order_items__product_info__product_parameter__parameter',
        ).annotate(
            total_sum=Sum(F('order_items__product_info__price') * F('order_items__quantity'))
        ).distinct()
        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

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

    def get(self, request):
        basket = Order.objects.filter(user_id=request.user.id).exclude(state='basket').prefetch_related(
            'order_items__product_info__product__category',
            'order_items__product_info__product_parameter__parameter',
        ).annotate(
            total_sum=Sum(F('order_items__product_info__price') * F('order_items__quantity'))
        ).distinct()
        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

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
                        update_order_state_signal.send(
                            sender=self.__class__,
                            user_id=request.user.id,
                            order_id=request.data['id']
                        )
                        return Response({'Status': True, 'detail': f'Заказ создан'},
                                        status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'Недостаточно аргументов'}, status=status.HTTP_400_BAD_REQUEST)
