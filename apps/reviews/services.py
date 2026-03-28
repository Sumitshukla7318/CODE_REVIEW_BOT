import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Files we don't want to send to AI for review
IGNORED_PATTERNS = [
    'package-lock.json',
    'yarn.lock',
    'poetry.lock',
    'Pipfile.lock',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot',
    'migrations/',
    '__pycache__',
    '.pyc',
    'node_modules/',
    '.min.js',
    '.min.css',
]

SYSTEM_PROMPT = """
You are an expert code reviewer. Analyze the provided code diff and return 
a JSON response with this exact structure:
{
  "summary": "2-3 sentence overview of what this PR does and overall quality",
  "issues": [
    {
      "file": "exact filename",
      "line": line_number_or_null,
      "severity": "critical|warning|suggestion",
      "type": "security|performance|style|logic|bug",
      "message": "Clear description of the issue",
      "suggestion": "Specific actionable fix"
    }
  ],
  "score": integer_0_to_100,
  "approved": true_or_false
}
Rules:
- score 90-100: excellent, approve
- score 70-89: good with minor issues
- score 50-69: needs work
- below 50: do not approve
- approved = true only if score >= 75
- Return ONLY valid JSON, no markdown, no explanation
"""


def should_ignore_file(filename: str) -> bool:
    """Check if a file should be excluded from AI review."""
    for pattern in IGNORED_PATTERNS:
        if pattern in filename:
            return True
    return False


def fetch_pr_files_from_github(owner: str, repo: str, pr_number: int) -> list:
    """
    Fetch changed files for a PR from GitHub API.
    Returns list of file dicts with filename, status, patch.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    headers = {
        'Accept': 'application/vnd.github.v3+json',
    }
    if settings.GITHUB_TOKEN:
        headers['Authorization'] = f"token {settings.GITHUB_TOKEN}"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def filter_files(files: list) -> list:
    """
    Filter out files that should not be reviewed.
    Returns only reviewable files with their patches.
    """
    filtered = []
    for f in files:
        filename = f.get('filename', '')
        patch = f.get('patch', '')

        if should_ignore_file(filename):
            logger.info(f"Skipping file: {filename}")
            continue

        if not patch:
            continue

        filtered.append({
            'filename': filename,
            'status': f.get('status', ''),
            'additions': f.get('additions', 0),
            'deletions': f.get('deletions', 0),
            'patch': patch,
        })

    return filtered


def build_review_prompt(filtered_files: list) -> str:
    """
    Build the prompt string to send to Groq API.
    Includes the diff of each reviewable file.
    """
    if not filtered_files:
        return "No reviewable files found in this PR."

    prompt_parts = ["Review the following code changes:\n"]

    for f in filtered_files:
        prompt_parts.append(f"### File: {f['filename']} ({f['status']})")
        prompt_parts.append(f"```diff\n{f['patch']}\n```\n")

    return '\n'.join(prompt_parts)

def call_groq_api(prompt: str) -> dict:
    """
    Send prompt to Groq API using direct HTTP request.
    Uses llama-3.1-8b-instant model (free tier).
    """
    import requests

    headers = {
        'Authorization': f"Bearer {settings.GROQ_API_KEY}",
        'Content-Type': 'application/json',
    }

    payload = {
        'model': 'llama-3.1-8b-instant',
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.1,
        'max_tokens': 2000,
    }

    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    return {
        'content': data['choices'][0]['message']['content'],
        'prompt_tokens': data['usage']['prompt_tokens'],
        'completion_tokens': data['usage']['completion_tokens'],
        'model': data['model'],
    }


def parse_ai_response(raw_response: str) -> dict:
    """
    Parse the AI JSON response into a structured dict.
    Falls back to a default structure if parsing fails.
    """
    try:
        # Strip any accidental markdown code fences
        cleaned = raw_response.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            cleaned = '\n'.join(lines[1:-1])

        parsed = json.loads(cleaned)

        # Validate required fields
        return {
            'summary': parsed.get('summary', 'No summary provided.'),
            'issues': parsed.get('issues', []),
            'score': int(parsed.get('score', 0)),
            'approved': bool(parsed.get('approved', False)),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AI response: {e}")
        logger.error(f"Raw response: {raw_response}")
        return {
            'summary': 'Failed to parse AI response.',
            'issues': [],
            'score': 0,
            'approved': False,
        }


def calculate_review_stats(repository) -> dict:
    """
    Calculate statistics for a repository's reviews.
    Returns aggregated data for the stats endpoint.
    """
    from django.db.models import Avg, Count
    from apps.reviews.models import CodeReview, ReviewIssue

    reviews = CodeReview.objects.filter(
        repository=repository,
        status=CodeReview.ReviewStatus.COMPLETED,
    )

    total_reviews = reviews.count()
    avg_score = reviews.aggregate(Avg('overall_score'))['overall_score__avg'] or 0

    issue_types = ReviewIssue.objects.filter(
        review__repository=repository,
    ).values('issue_type').annotate(
        count=Count('id')
    ).order_by('-count')

    files_with_issues = ReviewIssue.objects.filter(
        review__repository=repository,
    ).values('file_path').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    return {
        'total_reviews': total_reviews,
        'average_score': round(avg_score, 2),
        'most_common_issue_types': list(issue_types),
        'files_with_most_issues': list(files_with_issues),
    }