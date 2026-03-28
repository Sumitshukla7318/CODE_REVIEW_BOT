import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import UserFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.mark.django_db
class TestRegister:

    def test_register_success(self, client):
        url = reverse('auth-register')
        data = {
            'email': 'newuser@test.com',
            'username': 'newuser',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert response.data['data']['email'] == 'newuser@test.com'

    def test_register_password_mismatch(self, client):
        url = reverse('auth-register')
        data = {
            'email': 'newuser@test.com',
            'username': 'newuser',
            'password': 'StrongPass123!',
            'password2': 'WrongPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False

    def test_register_duplicate_email(self, client, user):
        url = reverse('auth-register')
        data = {
            'email': user.email,
            'username': 'anotheruser',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_email(self, client):
        url = reverse('auth-register')
        data = {
            'email': 'notanemail',
            'username': 'newuser',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, client, user):
        url = reverse('auth-login')
        data = {
            'email': user.email,
            'password': 'TestPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']

    def test_login_wrong_password(self, client, user):
        url = reverse('auth-login')
        data = {
            'email': user.email,
            'password': 'WrongPassword!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        url = reverse('auth-login')
        data = {
            'email': 'nobody@test.com',
            'password': 'TestPass123!',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogout:

    def test_logout_success(self, client, user):
        # Login first
        login_url = reverse('auth-login')
        login_response = client.post(
            login_url,
            {'email': user.email, 'password': 'TestPass123!'},
            format='json',
        )
        access = login_response.data['data']['access']
        refresh = login_response.data['data']['refresh']

        # Logout
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        logout_url = reverse('auth-logout')
        response = client.post(
            logout_url,
            {'refresh': refresh},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

    def test_logout_requires_auth(self, client):
        url = reverse('auth-logout')
        response = client.post(url, {'refresh': 'sometoken'}, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED