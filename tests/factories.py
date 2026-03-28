import factory
import factory.django
from django.contrib.auth import get_user_model
from apps.repositories.models import Repository
from apps.webhooks.models import WebhookEvent
from apps.reviews.models import PRDiff, CodeReview, ReviewIssue
from apps.repositories.services import generate_webhook_secret

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f'user{n}@test.com')
    username = factory.Sequence(lambda n: f'user{n}')
    password = factory.PostGenerationMethodCall('set_password', 'TestPass123!')

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        if create and results:
            instance.save()  # save after password is set
            
class RepositoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Repository

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f'repo{n}')
    owner = 'testowner'
    full_name = factory.LazyAttribute(lambda o: f'{o.owner}/{o.name}')
    github_url = factory.LazyAttribute(
        lambda o: f'https://github.com/{o.owner}/{o.name}'
    )
    webhook_secret = factory.LazyFunction(
        lambda: generate_webhook_secret()[1]  # returns encrypted secret
    )
    is_active = True


class WebhookEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WebhookEvent

    repository = factory.SubFactory(RepositoryFactory)
    event_type = 'pull_request'
    action = 'opened'
    pr_number = factory.Sequence(lambda n: n + 1)
    pr_title = 'Test PR'
    pr_author = 'testuser'
    head_sha = factory.Sequence(lambda n: f'sha{n}abc123')
    base_branch = 'main'
    head_branch = 'feature/test'
    raw_payload = {}
    status = WebhookEvent.EventStatus.PENDING


class PRDiffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PRDiff

    webhook_event = factory.SubFactory(WebhookEventFactory)
    files_changed = [
        {
            'filename': 'test.py',
            'status': 'added',
            'additions': 10,
            'deletions': 0,
            'patch': '+def test(): pass',
        }
    ]
    filtered_files = factory.LazyAttribute(lambda o: o.files_changed)
    total_additions = 10
    total_deletions = 0
    raw_diff = 'test diff'


class CodeReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CodeReview

    webhook_event = factory.SubFactory(WebhookEventFactory)
    pr_diff = factory.SubFactory(
        PRDiffFactory,
        webhook_event=factory.SelfAttribute('..webhook_event'),
    )
    repository = factory.LazyAttribute(lambda o: o.webhook_event.repository)
    summary = 'Test review summary'
    overall_score = 85
    approved = True
    model_used = 'llama-3.1-8b-instant'
    status = CodeReview.ReviewStatus.COMPLETED


class ReviewIssueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewIssue

    review = factory.SubFactory(CodeReviewFactory)
    file_path = 'test.py'
    line_number = 10
    severity = ReviewIssue.Severity.WARNING
    issue_type = ReviewIssue.IssueType.STYLE
    message = 'Test issue message'
    suggestion = 'Test suggestion'