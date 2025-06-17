from django.contrib import admin
from django.urls import path, include
from backend.views import (UserRegisterView, UserLogin, VerifyEmailView,
                           ContactView, ShopsView, CategoriesView, ProductInfoView,
                           PartnerState, PartnerOrders, PartnerUpdate, ShopUpdate)

urlpatterns = [
    path('user/register/', UserRegisterView.as_view(), name='api_user_register'),
    path('user/login/', UserLogin.as_view(), name='api_user_login'),
    path('user/confirm/', VerifyEmailView.as_view(), name='verify_email'),
    path('user/password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),
    path('user/contacts/', ContactView.as_view(), name='contacts_list'),
    path('user/contacts/<int:contact_id>/', ContactView.as_view(), name='contact_detail'),
    path('categories/', CategoriesView.as_view(), name='categories_list'),
    path('shops/', ShopsView.as_view(), name='shops_list'),
    path('products/', ProductInfoView.as_view(), name='products_list'),
    path('partner/state', PartnerState.as_view(), name='partner_state'),
    path('partner/update', PartnerUpdate.as_view(), name='partner_products_update'),
    path('partner/orders', PartnerOrders.as_view(), name='partner_orders'),
    path('partner/test', ShopUpdate.as_view(), name='partner_test'),

]
