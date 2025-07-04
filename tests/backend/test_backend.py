import pytest
from rest_framework.test import APIClient
from backend.models import User, EmailVerificationToken, Product, ProductInfo, Parameter, ProductParameter, \
    Shop, Order, OrderItem, Category, Contact
from yaml import safe_load
from django.utils import timezone
from datetime import timedelta

base_url = '/api/v1'


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def not_active_user():
    user = User.objects.create_user(email='12345@mail.ru',
                                    password='1234best_5',
                                    first_name='first',
                                    last_name='last',
                                    company='company',
                                    position='345345')
    EmailVerificationToken.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(hours=24)
    )
    return user


@pytest.fixture
def active_user():
    user = User.objects.create_user(email='1234@mail.ru',
                                    password='1234best_5',
                                    first_name='first',
                                    last_name='last',
                                    company='company',
                                    position='345345')
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def active_seller():
    user = User.objects.create_user(email='12345@mail.ru',
                                    password='1234best_5',
                                    first_name='first',
                                    last_name='last',
                                    company='company',
                                    position='345345',
                                    type='shop')
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def shop():
    file_path = 'shop1.yaml'
    with open(file_path, 'r', encoding='utf-8') as file:
        data = safe_load(file)

    shop = Shop.objects.create(name=data['shop'])
    for category in data['categories']:
        new_category, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
        new_category.shops.add(shop.id)
        new_category.save()
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

    return shop


@pytest.mark.django_db
def test_create_user(api_client):
    count = User.objects.count()
    data = {
        'email': '12345@mail.ru',
        'password': '1234best_5',
        'first_name': 'first',
        'last_name': 'last',
        'company': 'asdads',
        'position': '345345'
    }
    response = api_client.post(f"{base_url}/user/register", data=data)
    assert response.status_code == 200
    assert User.objects.count() == count + 1


@pytest.mark.django_db
def test_confirm_user(api_client, not_active_user):

    token = EmailVerificationToken.objects.filter(user_id=not_active_user.id).first()
    data = {
        'email': not_active_user.email,
        'token': token.token
    }
    assert User.objects.get(id=not_active_user.id).is_active is False
    response = api_client.post(f"{base_url}/user/register/confirm", data=data)
    # print(response.json())
    assert response.status_code == 200
    assert User.objects.get(id=not_active_user.id).is_active is True


@pytest.mark.django_db
def test_login_user(api_client, active_user):
    data = {
        'email': active_user.email,
    }
    response = api_client.post(f"{base_url}/user/login", data=data)
    assert response.status_code == 400

    data['password'] = '1'

    response = api_client.post(f"{base_url}/user/login", data=data)
    assert response.status_code == 400

    data['password'] = '1234best_5'
    response = api_client.post(f"{base_url}/user/login", data=data)
    # print(response.json())
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get('Token') is not None


@pytest.mark.django_db
def test_user_detail(api_client, active_user):
    response = api_client.get(f"{base_url}/user/detail")
    assert response.status_code == 401

    api_client.force_authenticate(user=active_user)
    response = api_client.get(f"{base_url}/user/detail")
    assert response.status_code == 200
    data = response.json()
    assert data.get('email') == active_user.email

    data = {
        'first_name': 'new_first_name'
    }
    response = api_client.post(f"{base_url}/user/detail", data=data)
    assert response.status_code == 200
    assert User.objects.get(id=active_user.id).first_name == data['first_name']


@pytest.mark.django_db
def test_contacts(api_client, active_user):
    response = api_client.get(f"{base_url}/user/contact")
    assert response.status_code == 401

    api_client.force_authenticate(user=active_user)

    data = {
        'city': 'city1',
        'street': 'street1',
        'house': 'house 1',
        'structure': 'structure 1',
        'building': 'building 1',
        'apartment': 'apartment 1',
        'phone': '132456789'
    }
    response = api_client.post(f"{base_url}/user/contact", data=data)
    assert response.status_code == 201

    response = api_client.get(f"{base_url}/user/contact")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1

    update_data = {
        'id': '1',
        'city': 'city2',
    }
    response = api_client.put(f"{base_url}/user/contact", data=update_data)
    assert response.status_code == 200

    response = api_client.get(f"{base_url}/user/contact")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data[0].get('city') == update_data['city']

    delete_data = {
        'items': '1',
    }
    response = api_client.delete(f"{base_url}/user/contact", data=delete_data)
    assert response.status_code == 200
    assert Contact.objects.filter(user_id=active_user.id).count() == 0


@pytest.mark.django_db
def test_get_categories(api_client):
    Category.objects.create(name='category1')
    response = api_client.get(f"{base_url}/categories")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == Category.objects.count()


@pytest.mark.django_db
def test_get_shops(api_client):
    Shop.objects.create(name='Shop1')
    response = api_client.get(f"{base_url}/shops")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == Shop.objects.count()


@pytest.mark.django_db
def test_partner_update(api_client, active_seller):
    api_client.force_authenticate(user=active_seller)
    data = {
        'url': 'https://raw.githubusercontent.com/netology-code/python-final-diplom/master/data/shop1.yaml',
    }
    response = api_client.post(f"{base_url}/partner/update", data=data)
    assert response.status_code == 200


@pytest.mark.django_db
def test_partner_state(api_client, active_seller):
    api_client.force_authenticate(user=active_seller)
    Shop.objects.create(name='shop1', user_id=active_seller.id)

    response = api_client.get(f"{base_url}/partner/state")
    assert response.status_code == 200
    data = response.json()
    assert data.get('state') is Shop.objects.get(user_id=active_seller.id).state
    data = {
        'state': 'False',
    }
    response = api_client.post(f"{base_url}/partner/state", data=data)
    assert response.status_code == 200
    assert Shop.objects.get(user_id=active_seller.id).state is False


@pytest.mark.django_db
def test_partner_orders(api_client, active_seller):
    api_client.force_authenticate(user=active_seller)
    Shop.objects.create(name='shop1', user_id=active_seller.id)

    response = api_client.get(f"{base_url}/partner/orders")
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_products(api_client, shop):

    response = api_client.get(f"{base_url}/products")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == Product.objects.count()

    test_shop_id = 1
    response = api_client.get(f"{base_url}/products?shop_id={test_shop_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == ProductInfo.objects.filter(shop_id=test_shop_id).count()

    test_category_id = 224
    response = api_client.get(f"{base_url}/products?category_id={test_category_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == ProductInfo.objects.filter(product__category_id=test_category_id).select_related(
        'shop', 'product__category').prefetch_related(
            'product_parameter__parameter').count()


@pytest.mark.django_db
def test_basket(api_client, active_user, shop):

    response = api_client.get(f"{base_url}/products")
    products = response.json()
    data = {
        'items': [{"product_info": products[0]['id'], "quantity": 2},
                  {"product_info": products[1]['id'], "quantity": 1}]
    }

    response = api_client.post(f"{base_url}/basket", data=data)
    assert response.status_code == 401

    api_client.force_authenticate(user=active_user)
    response = api_client.post(f"{base_url}/basket", data=data)
    assert response.status_code == 200

    assert Order.objects.filter(user_id=active_user.id, state='basket').count() == 1

    response = api_client.get(f"{base_url}/basket")
    assert response.status_code == 200
    response_data = response.json()
    basket = Order.objects.get(user_id=active_user.id, state='basket')
    basket_item_count = OrderItem.objects.filter(order_id=basket.id).count()
    assert len(response_data[0].get('order_items')) == len(data['items']) == basket_item_count

    update_data = {
        'items': [{"id": 1, "quantity": 4}, {"id": 2, "quantity": 6, }]
    }
    response = api_client.put(f"{base_url}/basket", data=update_data)
    assert response.status_code == 200

    for item in update_data['items']:
        assert OrderItem.objects.get(order_id=basket.id, id=item['id']).quantity == item['quantity']

    delete_data = {
        'items': '1'
    }
    response = api_client.delete(f"{base_url}/basket", data=delete_data)
    assert response.status_code == 200

    for item in delete_data['items'].split(','):
        assert OrderItem.objects.filter(order_id=basket.id, id=item).first() is None


@pytest.mark.django_db
def test_order(api_client, active_user, shop):
    api_client.force_authenticate(user=active_user)
    contact_data = {
        'city': 'city1',
        'street': 'street1',
        'phone': '132456789'
    }
    response = api_client.post(f"{base_url}/user/contact", data=contact_data)
    assert response.status_code == 201

    response = api_client.get(f"{base_url}/user/contact")
    contacts = response.json()
    contact_id = contacts[0].get('id')

    response = api_client.get(f"{base_url}/products")
    products = response.json()
    data = {
        'items': [{"product_info": products[0]['id'], "quantity": 2},
                  {"product_info": products[1]['id'], "quantity": 1}]
    }

    response = api_client.post(f"{base_url}/basket", data=data)
    assert response.status_code == 200

    basket = Order.objects.get(user_id=active_user.id, state='basket')

    data = {
        'id': str(basket.id),
        'contact': str(contact_id)
    }
    response = api_client.post(f"{base_url}/order", data=data)
    assert response.status_code == 200
    assert Order.objects.get(id=basket.id).state == 'new'

