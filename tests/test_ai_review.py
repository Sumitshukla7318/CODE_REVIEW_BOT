import pytest
from unittest.mock import patch, MagicMock
from apps.reviews.services import (
    parse_ai_response,
    build_review_prompt,
    filter_files,
    should_ignore_file,
)


class TestShouldIgnoreFile:

    def test_ignores_lock_files(self):
        assert should_ignore_file('package-lock.json') is True
        assert should_ignore_file('yarn.lock') is True
        assert should_ignore_file('poetry.lock') is True

    def test_ignores_images(self):
        assert should_ignore_file('logo.png') is True
        assert should_ignore_file('banner.jpg') is True
        assert should_ignore_file('icon.svg') is True

    def test_ignores_migrations(self):
        assert should_ignore_file('apps/users/migrations/0001_initial.py') is True

    def test_allows_python_files(self):
        assert should_ignore_file('views.py') is False
        assert should_ignore_file('models.py') is False
        assert should_ignore_file('services.py') is False

    def test_allows_js_files(self):
        assert should_ignore_file('app.js') is False

    def test_ignores_minified_files(self):
        assert should_ignore_file('bundle.min.js') is True


class TestFilterFiles:

    def test_filters_ignored_files(self):
        files = [
            {'filename': 'views.py', 'patch': '+def test(): pass', 'status': 'added', 'additions': 1, 'deletions': 0},
            {'filename': 'package-lock.json', 'patch': '+{}', 'status': 'modified', 'additions': 1, 'deletions': 0},
            {'filename': 'logo.png', 'patch': None, 'status': 'added', 'additions': 0, 'deletions': 0},
        ]
        result = filter_files(files)
        assert len(result) == 1
        assert result[0]['filename'] == 'views.py'

    def test_filters_files_without_patch(self):
        files = [
            {'filename': 'views.py', 'patch': None, 'status': 'added', 'additions': 1, 'deletions': 0},
        ]
        result = filter_files(files)
        assert len(result) == 0

    def test_returns_empty_for_all_ignored(self):
        files = [
            {'filename': 'package-lock.json', 'patch': '+{}', 'status': 'modified', 'additions': 1, 'deletions': 0},
        ]
        result = filter_files(files)
        assert len(result) == 0


class TestBuildReviewPrompt:

    def test_builds_prompt_with_files(self):
        files = [
            {
                'filename': 'views.py',
                'status': 'added',
                'additions': 5,
                'deletions': 0,
                'patch': '+def test(): pass',
            }
        ]
        prompt = build_review_prompt(files)
        assert 'views.py' in prompt
        assert 'def test(): pass' in prompt

    def test_empty_files_returns_message(self):
        prompt = build_review_prompt([])
        assert 'No reviewable files' in prompt


class TestParseAiResponse:

    def test_parses_valid_json(self):
        raw = '{"summary": "Good PR", "issues": [], "score": 90, "approved": true}'
        result = parse_ai_response(raw)
        assert result['summary'] == 'Good PR'
        assert result['score'] == 90
        assert result['approved'] is True
        assert result['issues'] == []

    def test_parses_json_with_markdown_fences(self):
        raw = '```json\n{"summary": "Good", "issues": [], "score": 85, "approved": true}\n```'
        result = parse_ai_response(raw)
        assert result['score'] == 85

    def test_handles_invalid_json(self):
        raw = 'This is not JSON at all'
        result = parse_ai_response(raw)
        assert result['score'] == 0
        assert result['approved'] is False
        assert result['summary'] == 'Failed to parse AI response.'

    def test_parses_issues(self):
        raw = '''{
            "summary": "Has issues",
            "issues": [
                {
                    "file": "views.py",
                    "line": 10,
                    "severity": "critical",
                    "type": "security",
                    "message": "SQL injection",
                    "suggestion": "Use parameterized queries"
                }
            ],
            "score": 40,
            "approved": false
        }'''
        result = parse_ai_response(raw)
        assert len(result['issues']) == 1
        assert result['issues'][0]['severity'] == 'critical'
        assert result['issues'][0]['type'] == 'security'

    def test_handles_missing_fields(self):
        raw = '{"score": 75}'
        result = parse_ai_response(raw)
        assert result['score'] == 75
        assert result['summary'] == 'No summary provided.'
        assert result['issues'] == []


@pytest.mark.django_db
class TestCallGroqApi:

    @patch('apps.reviews.services.requests.post')
    def test_successful_api_call(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"summary": "Good", "issues": [], "score": 90, "approved": true}'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50},
            'model': 'llama-3.1-8b-instant',
        }
        mock_post.return_value = mock_response

        from apps.reviews.services import call_groq_api
        result = call_groq_api('test prompt')

        assert result['prompt_tokens'] == 100
        assert result['completion_tokens'] == 50
        assert 'summary' in result['content']

    @patch('apps.reviews.services.requests.post')
    def test_api_failure_raises_exception(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.RequestException('API Error')

        from apps.reviews.services import call_groq_api
        with pytest.raises(requests.exceptions.RequestException):
            call_groq_api('test prompt')