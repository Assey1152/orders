from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django.contrib.auth.password_validation import validate_password
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from backend.serializers import UserSerializer, LoginSerializer, ContactSerializer, ShopSerializer, CategorySerializer, ProductInfoSerializer
from rest_framework import status
from .models import EmailVerificationToken, Contact, Shop, Product, Category, ProductInfo, Parameter, ProductParameter
from rest_framework.permissions import IsAuthenticated
from distutils.util import strtobool
from django.db.models import Q, Sum
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from requests import get
import yaml


# Create your views here.


class UserRegisterView(APIView):
    def post(self, request):
        if {'first_name', 'last_name', 'email', 'password'}.issubset(request.data):

            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class UserLogin(APIView):

    def post(self, request):

        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token, created = Token.objects.get_or_create(user=user)
            return JsonResponse({'Status': True, 'Token': token.key})
        return JsonResponse({'Status': False, 'Errors': 'Ошибка авторизации'})


class VerifyEmailView(APIView):

    def get(self, request):
        token = request.GET.get('token')
        if not token:
            return Response({'error': 'Токен не предоставлен'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification_token = EmailVerificationToken.objects.select_related('user').get(token=token)
        except EmailVerificationToken.DoesNotExist:
            return Response({'error': 'Неверный или просроченный токен'}, status=status.HTTP_400_BAD_REQUEST)

        if verification_token.is_expired():
            return Response({'error': 'Токен истек'}, status=status.HTTP_400_BAD_REQUEST)

        user = verification_token.user
        user.is_active = True
        user.save()
        verification_token.delete()  # Можно удалить после использования

        return Response({'message': 'Email успешно подтвержден'}, status=status.HTTP_200_OK)


class ContactView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_contact_by_id(self, contact_id, user):
        try:
            return Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return None

    def get(self, request, contact_id=None):
        if contact_id:
            contact = self.get_contact_by_id(contact_id, request.user)
            if contact:
                serializer = ContactSerializer(contact)
                return Response(serializer.data)
            else:
                return Response({'Status': False, 'Errors': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            contacts = Contact.objects.filter(user=request.user)
            serializer = ContactSerializer(contacts, many=True)
            return Response(serializer.data)

    def post(self, request):
        data = {**request.data, 'user': request.user.id}
        serializer = ContactSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True, **serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, contact_id):
        contact = self.get_contact_by_id(contact_id, request.user)
        if not contact:
            return Response({'Status': False, 'Errors': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ContactSerializer(contact, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True}, status=status.HTTP_200_OK)
        return Response({'Status': False, 'Errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, contact_id):
        if contact_id:
            contact = self.get_contact_by_id(contact_id, request.user)
            if contact:
                contact.delete()
                return Response({'Status': True}, status=status.HTTP_200_OK)
            else:
                return Response({'Status': False, 'Errors': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'Status': False, 'Errors': 'Contact id required'}, status=status.HTTP_400_BAD_REQUEST)


class CategoriesView(ListAPIView):
    """
    Класс для просмотра списка категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductInfoView(APIView):

    def get(self, request):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(category_id=category_id)
        queryset = ProductInfo.objects.filter(query).select_related('shop', 'product__category').prefetch_related('product_parameter__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class ShopsView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class PartnerState(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if request.user.type != 'shop':
            return Response({'Status': False, 'Errors': 'Only for partners'}, status=status.HTTP_403_FORBIDDEN)
        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request):
        if request.user.type != 'shop':
            return Response({'Status': False, 'Errors': 'Only for partners'}, status=status.HTTP_403_FORBIDDEN)
        new_state = request.data.get('state')
        if new_state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(new_state))
                return JsonResponse({'Status': True}, status=status.HTTP_200_OK)
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'Status': False, 'Errors': 'New state is required'}, status=status.HTTP_400_BAD_REQUEST)


class PartnerUpdate(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if request.user.type != 'shop':
            return Response({'Status': False, 'Errors': 'Only for partners'}, status=status.HTTP_403_FORBIDDEN)
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
                    product_parameter = ProductParameter.objects.create(parameter_id=parameter.id,
                                                                        product_info_id=product_info.id,
                                                                        value=value)
            return JsonResponse({'Status': True}, status=status.HTTP_200_OK)

        return Response({'Status': False, 'Errors': 'URL is required'}, status=status.HTTP_400_BAD_REQUEST)


class PartnerOrders(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if request.user.type != 'shop':
            return Response({'Status': False, 'Errors': 'Only for partners'}, status=status.HTTP_403_FORBIDDEN)


class ShopUpdate(APIView):
    def get(self, request):
        filepath = 'shop1.yaml'

        with open(filepath, 'r', encoding='utf-8') as file:
            yaml_content = yaml.safe_load(file)
            return Response(data=yaml_content)
