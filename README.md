# 🤖 AI Code Review Bot

> Self-hosted AI-powered code reviewer. Open a PR, get a review. Free. No subscriptions.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.x-green?style=flat-square)](https://djangoproject.com)
[![Tests](https://img.shields.io/badge/Tests-66%20passing-brightgreen?style=flat-square)](#testing)
[![Coverage](https://img.shields.io/badge/Coverage-79%25-brightgreen?style=flat-square)](#testing)
[![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)](LICENSE)

---

## Why I Built This

Every team has the same problem — PRs sitting in review queue for hours. Senior devs are busy. Junior devs miss bugs. Code quality is inconsistent — same issue caught on Monday, missed on Friday.

Paid tools like CodeRabbit fix this but cost $15/user/month. For a 10-person team that is $1,800 a year just to have a robot read code.

So I built my own. Self-hosted. Free AI via Groq. Works the same way.

**What it does:** Developer opens a PR → bot receives the webhook → fetches the diff → sends to AI → posts a structured review comment directly on the PR. Automatically. Every time.

---

## What the Review Looks Like

When you open a PR, the bot posts this comment automatically:

```
🤖 AI Code Review

Status: ❌ CHANGES REQUESTED
Score:  🔴 42/100
Model:  llama-3.1-8b-instant

📝 Summary
This PR adds a user data query function but contains a critical SQL injection
vulnerability and a hardcoded credential. Needs attention before merge.

🔍 Issues Found

🔴 Critical
  calculator.py
  Issue:   SQL injection — user_id injected directly into query string
  Fix:     Use parameterized queries: cursor.execute(query, (user_id,))

🔴 Critical
  calculator.py
  Issue:   Hardcoded password "admin123" visible in source code
  Fix:     Move to environment variables or a secrets manager

🟡 Warning
  calculator.py  Line 2
  Issue:   divide() has no zero-division guard
  Fix:     Add: if b == 0: raise ValueError("Cannot divide by zero")
```

Score below 75 means not approved. The AI caught SQL injection, hardcoded credentials, and a logic bug in a 10-line file.

---

## Architecture

```
Developer opens PR
        |
        | GitHub sends webhook
        v
POST /api/webhooks/github/
        |
        | 1. Verify HMAC-SHA256 signature
        | 2. Find registered repository in DB
        | 3. Store WebhookEvent  (status: PENDING)
        | 4. Queue Celery task
        | 5. Return 200 immediately
        |
        v
  [ Redis Queue ]
        |
        v
  Celery Worker
        |
        |-- Task 1: Validate PR action (opened / sync / reopened)
        |
        |-- Task 2: Fetch diff from GitHub API
        |           Filter lock files, images, migrations
        |           Store PRDiff in PostgreSQL
        |
        |-- Task 3: Build prompt from filtered diff
        |           Call Groq API  (LLaMA 3.1 — free tier)
        |           Parse JSON response
        |           Store CodeReview + ReviewIssues
        |           Post comment on GitHub PR
        |
        v
   WebhookEvent status → COMPLETED


Celery Beat runs two scheduled tasks:
  Every 5 minutes  →  auto-retry reviews stuck in PROCESSING
  Every night 2am  →  delete webhook logs older than 30 days
```

---

## Tech Stack

| Tool | Why this one |
|------|-------------|
| **Django 5.x** | FastAPI is faster but Django's ecosystem — JWT, Celery integration, DRF, ORM — saved weeks. For a CRUD-heavy API with auth, Django wins. |
| **Django REST Framework** | Serializers handle validation and transformation in one place. ViewSets give full CRUD in 10 lines. |
| **Celery + Redis** | GitHub expects a webhook response under 10 seconds. AI review takes 5–15 seconds. Without async, every webhook times out. Celery with Redis broker solves this cleanly. |
| **PostgreSQL** | JSONField for raw payloads, UUID primary keys, complex joins across 6 models. SQLite would not handle this. |
| **Groq API (LLaMA 3.1)** | Free tier. Sub-3 second responses. Catches SQL injections and hardcoded credentials reliably. The whole point is zero cost — paid alternatives defeat the purpose. |
| **Fernet Encryption** | Webhook secrets cannot be hashed — we need the plain value back for HMAC verification. Fernet gives reversible AES-128 encryption. Even if someone dumps the database, secrets are unreadable without the encryption key stored separately in env vars. |
| **pytest + factory-boy** | Creating test data with 6 linked models in 3 lines instead of 40. |

---

## How to Run Locally

### Requirements

- Python 3.11+
- PostgreSQL
- Redis

### Setup

```bash
git clone https://github.com/Sumitshukla7318/code-review-bot.git
cd code-review-bot

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

### Fill in `.env`

```env
# python -c "import secrets; print(secrets.token_hex(50))"
SECRET_KEY=your-secret-key

DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/code_review_bot
REDIS_URL=redis://localhost:6379/0

# Free at console.groq.com
GROQ_API_KEY=gsk_your_key

# github.com/settings/tokens → select repo scope
GITHUB_TOKEN=ghp_your_token

# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
WEBHOOK_SECRET_ENCRYPTION_KEY=your-fernet-key

DJANGO_SETTINGS_MODULE=config.settings.development
```

### Database

```bash
psql -U postgres -c "CREATE DATABASE code_review_bot;"
python manage.py migrate
```

### Start everything (3 terminals)

```bash
# Terminal 1 — Django server
python manage.py runserver

# Terminal 2 — Celery worker
celery -A config worker --loglevel=info

# Terminal 3 — Celery beat scheduler
celery -A config beat --loglevel=info
```

### Or Docker (one command)

```bash
docker-compose up --build
```

Starts PostgreSQL, Redis, Django, Celery worker, Celery beat all together.

### Verify

Open `http://localhost:8000/api/docs/` — Swagger UI with all endpoints.

---

## Connect a Real GitHub Repo

**Step 1 — Register your repo**

```bash
curl -X POST http://localhost:8000/api/repositories/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "your-repo",
    "owner": "your-github-username",
    "github_url": "https://github.com/your-username/your-repo"
  }'
```

Copy the `webhook_secret` from the response. **Shown only once.**

**Step 2 — Add webhook on GitHub**

Go to your repo → Settings → Webhooks → Add webhook

```
Payload URL:  https://your-domain.com/api/webhooks/github/
Content type: application/json
Secret:       paste the webhook_secret here
Events:       Pull requests only
```

**Step 3 — Open a PR**

The bot fetches the diff, reviews it, and posts the comment. Done.

---

## API Reference

**Auth**

```
POST   /api/auth/register/          Create account
POST   /api/auth/login/             Login, get JWT tokens
POST   /api/auth/token/refresh/     Refresh access token
POST   /api/auth/logout/            Blacklist refresh token
```

**Repositories**

```
GET    /api/repositories/                       List your repos
POST   /api/repositories/                       Register a repo
GET    /api/repositories/{id}/                  Repo detail
DELETE /api/repositories/{id}/                  Soft delete
POST   /api/repositories/{id}/rotate-secret/    Generate new webhook secret
GET    /api/repositories/{id}/stats/            Review statistics (cached)
GET    /api/repositories/{id}/reviews/          All reviews for this repo
```

**Reviews**

```
GET    /api/reviews/                     All reviews
GET    /api/reviews/?repo=name           Filter by repo
GET    /api/reviews/?pr_number=42        Filter by PR number
GET    /api/reviews/?severity=critical   Filter by issue severity
GET    /api/reviews/{id}/                Review detail with issues
GET    /api/reviews/{id}/issues/         Just the issues list
POST   /api/reviews/{id}/retry/          Retry a failed review
```

**Webhook**

```
POST   /api/webhooks/github/        GitHub webhook receiver
GET    /api/webhooks/events/        Inspect received events (debug)
```

---

## Testing

```bash
# All tests
pytest

# With coverage report
pytest --cov=apps --cov-report=term-missing

# One file
pytest tests/test_ai_review.py -v
```

**66 tests. 79% coverage.**

| File | What it covers |
|------|----------------|
| `test_webhook_signature.py` | HMAC verification — 7 edge cases including timing attack prevention |
| `test_webhook_receiver.py` | Full webhook flow, signature validation, ignored actions |
| `test_auth.py` | Register, login, logout, bad credentials |
| `test_repositories.py` | CRUD, soft delete, secret rotation, cross-user isolation |
| `test_ai_review.py` | File filtering, prompt building, JSON parsing edge cases |
| `test_review_api.py` | List filters, retry logic, ownership enforcement |
| `test_celery_tasks.py` | Task chain, error handling, retry backoff |

---

## Challenges and How I Solved Them

### request.body crash after request.data

Django reads the request body as a stream — once consumed, it is gone. DRF accesses `request.data` automatically for JSON parsing, which consumes the stream. Accessing `request.body` after that throws `RawPostDataException`. HMAC verification was silently failing on every webhook because of this.

**Fix:** Read `request.body` as the very first line of the webhook view, before anything else touches the request. One line change, one hour to debug.

---

### Webhook secrets — hash vs encrypt

First version stored a SHA-256 hash of the webhook secret. Looked secure. The problem: HMAC verification needs the plain secret, not the hash. You cannot reverse a hash. Signature verification failed 100% of the time in production.

**Fix:** Switched to Fernet symmetric encryption. Store ciphertext. Decrypt at verification time. Encryption key lives in environment variable, separate from the database.

---

### Groq model deprecated mid-development

`llama3-8b-8192` was decommissioned with no warning. Every API call returned 400. Switched to `llama-3.1-8b-instant`. Also replaced the Groq SDK with a direct `requests.post()` call to avoid SDK version conflicts going forward — raw HTTP does not deprecate.

---

### AI returning markdown instead of JSON

The system prompt says return only valid JSON. The model still wraps responses in markdown code fences sometimes. `json.loads()` on that throws an exception and crashes the task.

**Fix:** Strip markdown fences before parsing. If parsing still fails after that, return a safe default — score 0, approved false — instead of crashing the Celery task and losing the review.

---

### Celery task isolation

Celery's built-in `chain()` passes return values between tasks automatically but one task failure cascades and you lose the ability to retry individual tasks.

**Fix:** Each task writes its result to the database explicitly, then calls the next task with `.delay()`. Tasks are completely independent. Task 3 can be re-run alone via the retry endpoint without re-fetching the diff from GitHub.

---

### factory-boy password not saving in tests

`PostGenerationMethodCall('set_password', ...)` hashes the password after model creation. Newer factory-boy does not call `.save()` again after post-generation hooks. Every test login returned 401.

**Fix:** Override `_after_postgeneration()` in `UserFactory` to explicitly call `instance.save()` after the password is set.

---

## Review Scoring

```
90 - 100   Excellent     Auto-approved
75 -  89   Good          Approved with notes
50 -  74   Needs work    Not approved
 0 -  49   Critical      Blocked from merge
```

`approved = true` only when `score >= 75`

---

## Deploy to Render

1. Push code to GitHub
2. Render → New → Blueprint → connect your repo
3. Render reads `render.yaml` automatically — creates web service, worker, beat scheduler, PostgreSQL, Redis
4. Add three env vars in Render dashboard: `GROQ_API_KEY`, `GITHUB_TOKEN`, `WEBHOOK_SECRET_ENCRYPTION_KEY`
5. Deploy

---

## Project Structure

```
code_review_bot/
├── config/
│   ├── settings/
│   │   ├── base.py           shared settings
│   │   ├── development.py    local overrides
│   │   └── production.py     production + security headers
│   ├── celery.py             Celery app config
│   └── urls.py               root URL router
├── apps/
│   ├── core/                 base model, middleware, exceptions
│   ├── users/                custom user + JWT auth
│   ├── repositories/         repo registration + secret management
│   ├── webhooks/             webhook receiver + HMAC verification + Task 1
│   └── reviews/              diff fetch (Task 2) + AI review (Task 3) + REST API
├── tests/
│   ├── factories.py          test data factories
│   └── test_*.py             66 tests across 7 files
├── Dockerfile
├── docker-compose.yml
├── render.yaml
└── .github/workflows/ci.yml
```

---

Built by **Sumit Shukla** — [GitHub](https://github.com/Sumitshukla7318)
