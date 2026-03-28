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