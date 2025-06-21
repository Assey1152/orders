from django.core.management.base import BaseCommand
from backend.models import Shop, Parameter, Category, ProductInfo, Product, ProductParameter
from yaml import safe_load


class Command(BaseCommand):
    help = 'Загружает данные в БД из указанного файла.'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',  # Name of the argument
            type=str,  # Expected type of the argument
            help='Путь к файлу.'
        )

    def handle(self, *args, **options):

        file_path = options['file_path']
        with open(file_path, 'r', encoding='utf-8') as file:
            data = safe_load(file)
        if data:
            shop, _ = Shop.objects.get_or_create(name=data['shop'])
            for category in data['categories']:
                new_category, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                new_category.shops.add(shop.id)
                new_category.save()
            ProductInfo.objects.filter(shop_id=shop.id).delete()
            for item in data['goods']:
                product, _ = Product.objects.get_or_create(category_id=item['category'], name=item['name'])
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
