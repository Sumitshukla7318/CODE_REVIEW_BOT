import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def fetch_pr_diff(self, webhook_event_id: str):
    """
    Task 2 in the chain.
    Fetches code diff from GitHub API, filters files, stores PRDiff.
    Then chains to perform_ai_review.
    """
    from apps.webhooks.models import WebhookEvent
    from apps.reviews.models import PRDiff
    from apps.reviews.services import (
        fetch_pr_files_from_github,
        filter_files,
    )

    try:
        event = WebhookEvent.objects.select_related('repository').get(
            id=webhook_event_id
        )
    except WebhookEvent.DoesNotExist:
        logger.error(f"WebhookEvent {webhook_event_id} not found")
        return

    try:
        logger.info(f"Fetching diff for PR #{event.pr_number}")

        repo = event.repository
        files = fetch_pr_files_from_github(
            owner=repo.owner,
            repo=repo.name,
            pr_number=event.pr_number,
        )

        filtered = filter_files(files)

        total_additions = sum(f.get('additions', 0) for f in files)
        total_deletions = sum(f.get('deletions', 0) for f in files)

        pr_diff = PRDiff.objects.create(
            webhook_event=event,
            files_changed=files,
            total_additions=total_additions,
            total_deletions=total_deletions,
            filtered_files=filtered,
            raw_diff=str(files),
        )

        logger.info(
            f"Stored PRDiff {pr_diff.id} with "
            f"{len(filtered)} reviewable files"
        )

        # Chain to AI review task
        perform_ai_review.delay(str(pr_diff.id))

    except Exception as exc:
        logger.error(f"Error fetching diff for event {webhook_event_id}: {exc}")
        event.status = 'FAILED'
        event.error_message = str(exc)
        event.save(update_fields=['status', 'error_message'])
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def perform_ai_review(self, pr_diff_id: str):
    """
    Task 3 in the chain.
    Sends diff to Groq AI, parses response, stores CodeReview + ReviewIssues.
    """
    from apps.reviews.models import PRDiff, CodeReview, ReviewIssue
    from apps.reviews.services import (
        build_review_prompt,
        call_groq_api,
        parse_ai_response,
    )
    from django.core.cache import cache

    try:
        pr_diff = PRDiff.objects.select_related(
            'webhook_event__repository'
        ).get(id=pr_diff_id)
    except PRDiff.DoesNotExist:
        logger.error(f"PRDiff {pr_diff_id} not found")
        return

    event = pr_diff.webhook_event
    repository = event.repository

    # Create review record
    review = CodeReview.objects.create(
        webhook_event=event,
        pr_diff=pr_diff,
        repository=repository,
        status=CodeReview.ReviewStatus.PROCESSING,
    )

    try:
        # Check cache first — avoid re-reviewing same commit
        cache_key = f"review:{event.head_sha}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"Using cached review for SHA {event.head_sha}")
            parsed = cached
        else:
            # Build prompt and call Groq
            prompt = build_review_prompt(pr_diff.filtered_files)
            logger.info(f"Calling Groq API for PR #{event.pr_number}")

            groq_response = call_groq_api(prompt)
            parsed = parse_ai_response(groq_response['content'])

            # Update token counts
            review.prompt_tokens = groq_response['prompt_tokens']
            review.completion_tokens = groq_response['completion_tokens']
            review.model_used = groq_response['model']
            review.ai_raw_response = groq_response['content']

            # Cache for 1 hour
            cache.set(cache_key, parsed, timeout=3600)

        # Save review results
        review.summary = parsed['summary']
        review.overall_score = parsed['score']
        review.approved = parsed['approved']
        review.status = CodeReview.ReviewStatus.COMPLETED
        review.completed_at = timezone.now()
        review.save()

        # Save individual issues
        issues_to_create = []
        for issue in parsed.get('issues', []):
            severity = issue.get('severity', 'suggestion').lower()
            issue_type = issue.get('type', 'style').lower()

            # Validate choices
            valid_severities = ['critical', 'warning', 'suggestion']
            valid_types = ['security', 'performance', 'style', 'logic', 'bug']

            if severity not in valid_severities:
                severity = 'suggestion'
            if issue_type not in valid_types:
                issue_type = 'style'

            issues_to_create.append(ReviewIssue(
                review=review,
                file_path=issue.get('file', 'unknown'),
                line_number=issue.get('line'),
                severity=severity,
                issue_type=issue_type,
                message=issue.get('message', ''),
                suggestion=issue.get('suggestion', ''),
            ))

        ReviewIssue.objects.bulk_create(issues_to_create)

        # Update webhook event status
        event.status = 'COMPLETED'
        event.processed_at = timezone.now()
        event.save(update_fields=['status', 'processed_at'])

        logger.info(
            f"Review completed for PR #{event.pr_number} "
            f"score={parsed['score']} issues={len(issues_to_create)}"
        )
        # Post review as GitHub PR comment
        try:
            from apps.reviews.github import post_review_comment
            post_review_comment(
                owner=repository.owner,
                repo=repository.name,
                pr_number=event.pr_number,
                review=review,
            )
        except Exception as e:
            logger.error(f"Failed to post GitHub PR comment: {e}")
            # Don't fail the whole task just because comment failed

    except Exception as exc:
        logger.error(f"Error performing AI review {pr_diff_id}: {exc}")
        review.status = CodeReview.ReviewStatus.FAILED
        review.error_message = str(exc)
        review.save(update_fields=['status', 'error_message'])

        event.status = 'FAILED'
        event.error_message = str(exc)
        event.save(update_fields=['status', 'error_message'])

        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 120)
    

@shared_task
def check_pending_reviews():
    """
    Periodic task — runs every 5 minutes.
    Finds stuck reviews (PENDING/PROCESSING > 10 mins) and retries them.
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.reviews.models import CodeReview

    cutoff = timezone.now() - timedelta(minutes=10)

    stuck_reviews = CodeReview.objects.filter(
        status__in=[
            CodeReview.ReviewStatus.PENDING,
            CodeReview.ReviewStatus.PROCESSING,
        ],
        created_at__lt=cutoff,
    ).select_related('pr_diff')

    count = stuck_reviews.count()

    for review in stuck_reviews:
        logger.warning(f"Retrying stuck review {review.id}")
        review.status = CodeReview.ReviewStatus.PENDING
        review.save(update_fields=['status'])
        perform_ai_review.delay(str(review.pr_diff.id))

    logger.info(f"Retried {count} stuck reviews")
    return count