from django.contrib import admin
from .models import User, Category, Shop, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, EmailVerificationToken
# Register your models here.


class CategoryInline(admin.TabularInline):
    model = Category.shops.through
    extra = 0


class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 0


class ProductInfoInline(admin.TabularInline):
    model = ProductInfo
    extra = 0


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'position', 'type')
    inlines = (ContactInline, )


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    pass


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', )
    inlines = (CategoryInline, )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'state', 'url')
    inlines = (CategoryInline, ProductInfoInline, )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category')
    inlines = (ProductInfoInline, )


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'model', 'ext_id', 'quantity', 'price', 'price_rrc', 'image')


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    inlines = (ProductParameterInline, )


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'state', 'contact')
    inlines = (OrderItemInline, )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_info', 'quantity')


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at')
