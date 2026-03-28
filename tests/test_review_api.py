import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import (
    UserFactory,
    RepositoryFactory,
    WebhookEventFactory,
    PRDiffFactory,
    CodeReviewFactory,
    ReviewIssueFactory,
)
from apps.reviews.models import CodeReview
from unittest.mock import patch


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


@pytest.fixture
def review(repository):
    event = WebhookEventFactory(repository=repository)
    diff = PRDiffFactory(webhook_event=event)
    return CodeReviewFactory(
        webhook_event=event,
        pr_diff=diff,
        repository=repository,
    )


@pytest.mark.django_db
class TestReviewList:

    def test_list_reviews(self, auth_client, review):
        url = reverse('reviews-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert len(response.data['data']) == 1

    def test_filter_by_repo(self, auth_client, review, repository):
        url = reverse('reviews-list')
        response = auth_client.get(url, {'repo': repository.name})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 1

    def test_filter_by_pr_number(self, auth_client, review):
        url = reverse('reviews-list')
        response = auth_client.get(
            url,
            {'pr_number': review.webhook_event.pr_number},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 1

    def test_filter_by_nonexistent_pr(self, auth_client, review):
        url = reverse('reviews-list')
        response = auth_client.get(url, {'pr_number': 99999})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0

    def test_list_requires_auth(self, client):
        url = reverse('reviews-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestReviewDetail:

    def test_retrieve_review(self, auth_client, review):
        url = reverse('reviews-detail', kwargs={'pk': review.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['id'] == str(review.id)
        assert response.data['data']['overall_score'] == review.overall_score

    def test_cannot_access_other_users_review(self, auth_client):
        other_review = CodeReviewFactory()
        url = reverse('reviews-detail', kwargs={'pk': other_review.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReviewIssues:

    def test_get_review_issues(self, auth_client, review):
        ReviewIssueFactory(review=review)
        ReviewIssueFactory(review=review)

        url = reverse('reviews-issues', kwargs={'pk': review.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 2

    def test_issues_empty_when_none(self, auth_client, review):
        url = reverse('reviews-issues', kwargs={'pk': review.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0


@pytest.mark.django_db
class TestReviewRetry:
    @patch('apps.reviews.tasks.perform_ai_review.delay')
    def test_retry_failed_review(self, mock_task, auth_client, review):
        review.status = CodeReview.ReviewStatus.FAILED
        review.save()

        url = reverse('reviews-retry', kwargs={'pk': review.id})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert mock_task.called is True

    def test_cannot_retry_completed_review(self, auth_client, review):
        review.status = CodeReview.ReviewStatus.COMPLETED
        review.save()

        url = reverse('reviews-retry', kwargs={'pk': review.id})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST