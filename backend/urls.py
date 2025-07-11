from django.contrib import admin
from django.urls import path, include
from backend.views import (UserRegisterView, UserLoginView, VerifyEmailView, UserDetailView, ResetPasswordRequestView,
                           ContactView, ShopsView, CategoriesView, ProductInfoView, GithubLoginView,
                           PartnerState, PartnerOrders, PartnerUpdate,
                           BasketView, OrderView,
                           SentryDebug)
from django_rest_passwordreset.views import ResetPasswordConfirm
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from django.urls import path


urlpatterns = [
    path('user/register', UserRegisterView.as_view(), name='api_user_register'),
    path('user/register/confirm', VerifyEmailView.as_view(), name='verify_email'),
    path('user/login', UserLoginView.as_view(), name='user_login'),
    path('user/detail', UserDetailView.as_view(), name='user_detail'),
    path('user/password_reset', ResetPasswordRequestView.as_view(), name='password_reset'),
    path('user/password_reset/confirm', ResetPasswordConfirm.as_view(), name='password_reset_confirm'),
    path('user/contact', ContactView.as_view(), name='contacts_list'),
    path('partner/state', PartnerState.as_view(), name='partner_state'),
    path('partner/update', PartnerUpdate.as_view(), name='partner_products_update'),
    path('partner/orders', PartnerOrders.as_view(), name='partner_orders'),
    path('categories', CategoriesView.as_view(), name='categories_list'),
    path('shops', ShopsView.as_view(), name='shops_list'),
    path('products', ProductInfoView.as_view(), name='products_list'),
    path('basket', BasketView.as_view(), name='basket'),
    path('order', OrderView.as_view(), name='order_list'),
    # drf-spectacular urls
    path('schema', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # social-auth path
    path("", include('social_django.urls', namespace="social")),
    path('user/login/github', GithubLoginView.as_view(), name='social_github_login'),
    # Sentry test
    path('sentry-debug/', SentryDebug.as_view()),
]
