import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def post_review_comment(owner: str, repo: str, pr_number: int, review) -> bool:
    """
    Post AI review results as a comment on the GitHub PR.
    Returns True if successful, False otherwise.
    """
    if not settings.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — skipping PR comment")
        return False

    comment_body = format_review_comment(review)

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        'Authorization': f"token {settings.GITHUB_TOKEN}",
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    }

    response = requests.post(
        url,
        headers=headers,
        json={'body': comment_body},
        timeout=30,
    )

    if response.status_code == 201:
        logger.info(f"Posted review comment on PR #{pr_number}")
        return True
    else:
        logger.error(
            f"Failed to post PR comment: {response.status_code} {response.text}"
        )
        return False


def format_review_comment(review) -> str:
    """
    Format the AI review into a readable GitHub PR comment using markdown.
    """
    # Score emoji
    if review.overall_score >= 90:
        score_emoji = '🟢'
    elif review.overall_score >= 70:
        score_emoji = '🟡'
    elif review.overall_score >= 50:
        score_emoji = '🟠'
    else:
        score_emoji = '🔴'

    approved_text = '✅ **APPROVED**' if review.approved else '❌ **CHANGES REQUESTED**'

    lines = [
        '## 🤖 AI Code Review',
        '',
        f'**Status:** {approved_text}',
        f'**Score:** {score_emoji} {review.overall_score}/100',
        f'**Model:** `{review.model_used}`',
        '',
        '### 📝 Summary',
        review.summary,
        '',
    ]

    issues = review.issues.all()

    if issues:
        lines.append('### 🔍 Issues Found')
        lines.append('')

        # Group by severity
        critical = [i for i in issues if i.severity == 'critical']
        warnings = [i for i in issues if i.severity == 'warning']
        suggestions = [i for i in issues if i.severity == 'suggestion']

        if critical:
            lines.append('#### 🔴 Critical')
            for issue in critical:
                lines.append(f'- **`{issue.file_path}`**')
                if issue.line_number:
                    lines.append(f'  - Line: {issue.line_number}')
                lines.append(f'  - **Issue:** {issue.message}')
                lines.append(f'  - **Fix:** {issue.suggestion}')
                lines.append('')

        if warnings:
            lines.append('#### 🟡 Warnings')
            for issue in warnings:
                lines.append(f'- **`{issue.file_path}`**')
                if issue.line_number:
                    lines.append(f'  - Line: {issue.line_number}')
                lines.append(f'  - **Issue:** {issue.message}')
                lines.append(f'  - **Fix:** {issue.suggestion}')
                lines.append('')

        if suggestions:
            lines.append('#### 💡 Suggestions')
            for issue in suggestions:
                lines.append(f'- **`{issue.file_path}`**')
                lines.append(f'  - **Issue:** {issue.message}')
                lines.append(f'  - **Fix:** {issue.suggestion}')
                lines.append('')
    else:
        lines.append('### ✅ No Issues Found')
        lines.append('')

    lines.extend([
        '---',
        '*Powered by [AI Code Review Bot](https://github.com/Sumitshukla7318)*',
    ])

    return '\n'.join(lines)

def post_failure_comment(owner: str, repo: str, pr_number: int, error_message: str, review_id: str) -> bool:
    """
    Post a failure comment on the GitHub PR when AI review fails.
    Called from the except block of perform_ai_review task.
    """
    if not settings.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — skipping failure comment")
        return False

    comment_body = format_failure_comment(error_message, review_id)

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        'Authorization': f"token {settings.GITHUB_TOKEN}",
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    }

    response = requests.post(
        url,
        headers=headers,
        json={'body': comment_body},
        timeout=30,
    )

    if response.status_code == 201:
        logger.info(f"Posted failure comment on PR #{pr_number}")
        return True
    else:
        logger.error(f"Failed to post failure comment: {response.status_code} {response.text}")
        return False


def format_failure_comment(error_message: str, review_id: str) -> str:
    """
    Format a clean failure message for the GitHub PR comment.
    Tells the developer what went wrong and what to do next.
    """
    # Detect the type of error and give a human-readable reason
    if 'groq' in error_message.lower() or 'api' in error_message.lower():
        reason = "Groq AI API failed or timed out"
        tip = "This is usually temporary. The review has been queued for automatic retry."
    elif 'github' in error_message.lower() or 'diff' in error_message.lower():
        reason = "Could not fetch the diff from GitHub API"
        tip = "Check that your GitHub token has repo read access."
    elif 'timeout' in error_message.lower():
        reason = "Request timed out waiting for AI response"
        tip = "This is usually temporary. Retry will happen automatically."
    elif 'json' in error_message.lower() or 'parse' in error_message.lower():
        reason = "AI returned an unexpected response format"
        tip = "The review will be retried automatically."
    else:
        reason = "An unexpected error occurred during review"
        tip = "The review has been queued for automatic retry."

    lines = [
        "## 🤖 AI Code Review — Failed",
        "",
        "❌ The automated review could not be completed.",
        "",
        f"**Reason:** {reason}",
        "",
        f"**What happens next:** {tip}",
        "",
        "**Manual retry:** If the problem persists, you can trigger a manual retry:",
        f"```",
        f"POST /api/reviews/{review_id}/retry/",
        f"```",
        "",
        "---",
        "",
        "<details>",
        "<summary>Technical details (click to expand)</summary>",
        "",
        "```",
        f"{error_message[:300]}",  # cap at 300 chars — no giant stack traces on PR
        "```",
        "",
        "</details>",
        "",
        "---",
        "*Powered by [AI Code Review Bot](https://github.com/Sumitshukla7318)*",
    ]

    return '\n'.join(lines)