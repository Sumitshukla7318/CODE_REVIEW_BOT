import pytest
import hmac
import hashlib
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch
from tests.factories import UserFactory, RepositoryFactory
from apps.repositories.services import decrypt_secret


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def repository(user):
    return RepositoryFactory(user=user)


def make_signature(payload: bytes, plain_secret: str) -> str:
    return 'sha256=' + hmac.new(
        plain_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()


def make_pr_payload(repo_name='testrepo', repo_owner='testowner', action='opened'):
    return {
        'action': action,
        'number': 1,
        'pull_request': {
            'title': 'Test PR',
            'user': {'login': 'testuser'},
            'head': {'sha': 'abc123', 'ref': 'feature'},
            'base': {'ref': 'main'},
        },
        'repository': {
            'name': repo_name,
            'owner': {'login': repo_owner},
        },
    }


@pytest.mark.django_db
class TestGithubWebhookView:

    def test_ping_event(self, client):
        url = reverse('github-webhook')
        response = client.post(
            url,
            data='{}',
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='ping',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['message'] == 'pong'

    def test_unsupported_event(self, client):
        url = reverse('github-webhook')
        response = client.post(
            url,
            data='{}',
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='push',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unregistered_repository(self, client):
        url = reverse('github-webhook')
        payload = make_pr_payload('unknown-repo', 'unknown-owner')
        body = json.dumps(payload).encode()
        response = client.post(
            url,
            data=body,
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='pull_request',
            HTTP_X_HUB_SIGNATURE_256='sha256=fakesig',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('apps.webhooks.tasks.process_webhook_event.delay')
    def test_valid_webhook(self, mock_task, client, repository):
        # Get plain secret by decrypting stored secret
        plain_secret = decrypt_secret(repository.webhook_secret)

        payload = make_pr_payload(repository.name, repository.owner)
        body = json.dumps(payload).encode()
        signature = make_signature(body, plain_secret)

        url = reverse('github-webhook')
        response = client.post(
            url,
            data=body,
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='pull_request',
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert mock_task.called is True

    def test_invalid_signature(self, client, repository):
        payload = make_pr_payload(repository.name, repository.owner)
        body = json.dumps(payload).encode()

        url = reverse('github-webhook')
        response = client.post(
            url,
            data=body,
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='pull_request',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalidsignature',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('apps.webhooks.tasks.process_webhook_event.delay')
    def test_ignored_action(self, mock_task, client, repository):
        plain_secret = decrypt_secret(repository.webhook_secret)
        payload = make_pr_payload(
            repository.name,
            repository.owner,
            action='closed',
        )
        body = json.dumps(payload).encode()
        signature = make_signature(body, plain_secret)

        url = reverse('github-webhook')
        response = client.post(
            url,
            data=body,
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='pull_request',
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        assert response.status_code == status.HTTP_200_OK
        assert mock_task.called is False