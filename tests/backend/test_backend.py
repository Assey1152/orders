import pytest
from rest_framework.test import APIClient
from backend.models import User, EmailVerificationToken, Product, ProductInfo, Parameter, ProductParameter, Shop, Order, OrderItem, Category, Contact
from rest_framework.authtoken.models import Token

base_url = '/api/v1'


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def buyer():
    return User.objects.create_user(email='1234@mail.ru',
                                    password='1234best_5',
                                    first_name='first',
                                    last_name='last',
                                    company='company',
                                    position='345345')


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
def authenticated_user(api_client, active_user):
    user = active_user
    api_client.force_authenticate(user=user)
    return user


@pytest.mark.skip
@pytest.mark.django_db
def test_create_user(api_client):
    count = User.objects.count()
    data = {
        'email': '1234@mail.ru',
        'password': '1234best_5',
        'first_name': 'first',
        'last_name': 'last',
        'company': 'asdads',
        'position': '345345'
    }
    response = api_client.post(f"{base_url}/user/register", data=data)
    assert response.status_code == 200
    assert User.objects.count() == count + 1


@pytest.mark.skip
@pytest.mark.django_db
def test_confirm_user(api_client, buyer):
    token = EmailVerificationToken.objects.filter(user_id=buyer.id).first()
    data = {
        'email': buyer.email,
        'token': token.token
    }
    assert User.objects.get(id=buyer.id).is_active is False
    response = api_client.post(f"{base_url}/user/register/confirm", data=data)
    # print(response.json())
    assert response.status_code == 200
    assert User.objects.get(id=buyer.id).is_active is True


@pytest.mark.skip
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


@pytest.mark.skip
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


@pytest.mark.skip
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


@pytest.mark.skip
@pytest.mark.django_db
def test_get_categories(api_client):
    Category.objects.create(name='category1')
    response = api_client.get(f"{base_url}/categories")
    response_data = response.json()
    assert len(response_data) == Category.objects.count()


@pytest.mark.django_db
def test_get_shops(api_client):
    Shop.objects.create(name='Shop1')
    response = api_client.get(f"{base_url}/shops")
    response_data = response.json()
    assert len(response_data) == Shop.objects.count()




