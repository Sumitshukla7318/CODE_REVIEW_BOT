import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import UserFactory, RepositoryFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(client, user):
    login_url = reverse('auth-login')
    response = client.post(
        login_url,
        {'email': user.email, 'password': 'TestPass123!'},
        format='json',
    )
    token = response.data['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def repository(user):
    return RepositoryFactory(user=user)


@pytest.mark.django_db
class TestRepositoryList:

    def test_list_repositories(self, auth_client, repository):
        url = reverse('repositories-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert len(response.data['data']) == 1

    def test_list_requires_auth(self, client):
        url = reverse('repositories-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_only_sees_own_repos(self, auth_client, user):
        # Another user's repo
        other_user = UserFactory()
        RepositoryFactory(user=other_user)

        url = reverse('repositories-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0


@pytest.mark.django_db
class TestRepositoryCreate:

    def test_create_repository(self, auth_client):
        url = reverse('repositories-list')
        data = {
            'name': 'my-repo',
            'owner': 'myusername',
            'github_url': 'https://github.com/myusername/my-repo',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert response.data['data']['name'] == 'my-repo'
        assert response.data['data']['full_name'] == 'myusername/my-repo'
        # Plain secret shown once on creation
        assert 'webhook_secret' in response.data['data']

    def test_create_duplicate_repository(self, auth_client, user, repository):
        url = reverse('repositories-list')
        data = {
            'name': repository.name,
            'owner': repository.owner,
            'github_url': repository.github_url,
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestRepositoryDetail:

    def test_retrieve_repository(self, auth_client, repository):
        url = reverse('repositories-detail', kwargs={'pk': repository.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['id'] == str(repository.id)

    def test_delete_repository(self, auth_client, repository):
        url = reverse('repositories-detail', kwargs={'pk': repository.id})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_200_OK

        # Verify soft deleted
        repository.refresh_from_db()
        assert repository.is_active is False

    def test_cannot_access_other_users_repo(self, auth_client):
        other_repo = RepositoryFactory()
        url = reverse('repositories-detail', kwargs={'pk': other_repo.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestRotateSecret:

    def test_rotate_secret(self, auth_client, repository):
        old_secret = repository.webhook_secret
        url = reverse('repositories-rotate-secret', kwargs={'pk': repository.id})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        repository.refresh_from_db()
        assert repository.webhook_secret != old_secret