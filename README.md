<div align="center">

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🤖  AI CODE REVIEW BOT                         ║
║                                                           ║
║     Self-hosted. AI-powered. Free.                        ║
║     Your pull requests reviewed before coffee gets cold.  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

---

## The Problem

Every team I've seen has the same bottleneck — **pull requests waiting for review**.

Senior developers are busy. Junior developers miss security bugs. Code review is inconsistent — same issue gets caught on Monday, missed on Friday. And paid tools like CodeRabbit start at $15/month per user. For a 10-person team that's $150/month just to have a robot read your code.

So I built my own.

**AI Code Review Bot** is a self-hosted backend system that:
- Receives GitHub PR events via webhook
- Fetches the code diff automatically
- Sends it to an AI model for structured review
- Posts the feedback directly on your PR as a comment
- Stores everything so you can query, filter, and track over time

Zero dollars. Runs on your own server. Works in minutes.

---

## What It Actually Does

Open a PR → bot posts this on it automatically:

```
🤖 AI Code Review

Status: ❌ CHANGES REQUESTED
Score:  🔴 42/100
Model:  llama-3.1-8b-instant

📝 Summary
This PR adds a user data query function but contains a critical SQL injection
vulnerability and a hardcoded credential. Needs immediate attention before merge.

🔍 Issues Found

🔴 Critical
  calculator.py
  Issue:  SQL injection — user_id injected directly into query string
  Fix:    Use parameterized queries: cursor.execute(query, (user_id,))

🔴 Critical
  calculator.py
  Issue:  Hardcoded password "admin123" visible in source code
  Fix:    Move to environment variables or a secrets manager

🟡 Warning
  calculator.py  Line 2
  Issue:  divide() has no zero-division guard
  Fix:    Add: if b == 0: raise ValueError("Cannot divide by zero")
```

> The AI caught SQL injection, hardcoded credentials, and a division bug in a 10-line file.
> Score 42 = blocked from merge. That's the point.

---

## Architecture

```
                        ┌─────────────────────┐
                        │     GitHub          │
                        │   Pull Request      │
                        └──────────┬──────────┘
                                   │ webhook POST
                                   ▼
┌──────────────────────────────────────────────────────────┐
│                    DJANGO API SERVER                      │
│                                                          │
│  POST /api/webhooks/github/                              │
│  ┌─────────────────────────────────────────────────┐     │
│  │ 1. Read raw body (before parsing — critical)    │     │
│  │ 2. Verify HMAC-SHA256 signature                 │     │
│  │ 3. Decrypt webhook secret from DB               │     │
│  │ 4. Validate PR action (opened/sync/reopened)    │     │
│  │ 5. Store WebhookEvent → status: PENDING         │     │
│  │ 6. Queue Celery task → return 200 immediately   │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────────┬───────────────────────────────┘
                           │ .delay() → Redis queue
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   CELERY WORKER                          │
│                                                          │
│  Task 1: process_webhook_event()                         │
│  └── validates event, sets PROCESSING status            │
│      └── chains to Task 2                               │
│                                                          │
│  Task 2: fetch_pr_diff()                                │
│  └── calls GitHub API → gets changed files              │
│      └── filters: removes lock files, images, migrations │
│          └── stores PRDiff → chains to Task 3           │
│                                                          │
│  Task 3: perform_ai_review()                            │
│  └── checks Redis cache (same commit = skip AI)         │
│      └── builds structured prompt                       │
│          └── calls Groq API (LLaMA 3.1)                 │
│              └── parses JSON response                   │
│                  └── stores CodeReview + ReviewIssues   │
│                      └── posts comment on GitHub PR     │
└──────────────────────────┬───────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        PostgreSQL       Redis       GitHub PR
        (reviews,       (cache +     (comment
         issues)         broker)      posted)
```

**Celery Beat** (separate scheduler process) runs two background tasks:
- Every 5 minutes → auto-retry stuck reviews
- Every night at 2am → clean up webhook logs older than 30 days

---

## Tech Stack

I didn't pick tools randomly. Here's the reasoning behind each choice:

| Tool | Why this, not something else |
|------|------------------------------|
| **Django 5.x** | Battle-tested ORM, admin panel, migrations. FastAPI is faster but Django's ecosystem (simplejwt, celery integration, DRF) saved weeks of work. For a CRUD-heavy API with auth, Django wins. |
| **Django REST Framework** | Serializers handle validation + transformation in one place. ViewSets give you CRUD with 10 lines. The alternative was writing all of that by hand. |
| **Celery + Redis** | GitHub expects a webhook response in under 10 seconds. AI review takes 5-15 seconds. Without async processing, every webhook would time out. Celery with Redis broker was the obvious answer — battle-tested, Django-native. |
| **PostgreSQL** | JSONField for raw payloads, UUID primary keys, complex queries with joins across 6 models. SQLite would have buckled. PostgreSQL handles all of it. |
| **Groq API (LLaMA 3.1)** | Free tier. Genuinely fast (sub-3s responses). The llama-3.1-8b-instant model is good enough to catch SQL injections and hardcoded credentials. Paid alternatives (GPT-4, Claude) cost money. The whole point of this project is zero cost. |
| **Fernet Encryption** | Webhook secrets can't be stored as plain text or even hashed. We need to recover them for HMAC verification. Fernet (AES-128-CBC + HMAC) gives us reversible encryption with authenticated encryption — can't decrypt without the key, can't tamper without detection. |
| **drf-spectacular** | Auto-generates OpenAPI schema from code. Zero manual documentation. Swagger UI works out of the box. |
| **factory-boy** | Creating realistic test data with relationships (user → repo → webhook → diff → review → issues) in 3 lines instead of 40. |

---

## How to Run Locally

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis

### 1. Clone and set up

```bash
git clone https://github.com/Sumitshukla7318/code-review-bot.git
cd code-review-bot

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Generate this:
# python -c "import secrets; print(secrets.token_hex(50))"
SECRET_KEY=your-secret-key-here

DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Your local PostgreSQL
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/code_review_bot

# Redis (default if running locally)
REDIS_URL=redis://localhost:6379/0

# Free at console.groq.com
GROQ_API_KEY=gsk_your_key_here

# github.com/settings/tokens → select repo scope
GITHUB_TOKEN=ghp_your_token_here

# Generate this:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
WEBHOOK_SECRET_ENCRYPTION_KEY=your-fernet-key-here

DJANGO_SETTINGS_MODULE=config.settings.development
```

### 3. Database setup

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE code_review_bot;"

# Run migrations
python manage.py migrate

# (Optional) Create admin user
python manage.py createsuperuser
```

### 4. Start all three processes

Open three terminals:

```bash
# Terminal 1 — Django server
python manage.py runserver

# Terminal 2 — Celery worker (processes tasks)
celery -A config worker --loglevel=info

# Terminal 3 — Celery beat (periodic tasks)
celery -A config beat --loglevel=info
```

### 5. Or use Docker (one command)

```bash
cp .env.example .env
# Fill in GROQ_API_KEY, GITHUB_TOKEN, WEBHOOK_SECRET_ENCRYPTION_KEY

docker-compose up --build
```

Everything starts automatically: PostgreSQL, Redis, Django, Celery worker, Celery beat.

### 6. Verify it's working

```bash
# Check Swagger docs
open http://localhost:8000/api/docs/

# Register an account
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","username":"you","password":"Test1234!","password2":"Test1234!"}'

# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"Test1234!"}'
```

---

## Connecting a Real GitHub Repository

**Step 1 — Register your repo**
```bash
curl -X POST http://localhost:8000/api/repositories/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "your-repo-name",
    "owner": "your-github-username",
    "github_url": "https://github.com/your-github-username/your-repo-name"
  }'
```

Copy the `webhook_secret` from the response. **This is shown only once.**

**Step 2 — Add webhook on GitHub**

Go to: `https://github.com/your-username/your-repo/settings/hooks/new`

```
Payload URL:   https://your-server.com/api/webhooks/github/
Content type:  application/json
Secret:        [paste webhook_secret from Step 1]
Events:        ✅ Pull requests
```

**Step 3 — Open a PR**

The bot will:
1. Receive the event (< 100ms)
2. Fetch the diff (1-3s)
3. Review with AI (3-10s)
4. Post comment on your PR (< 1s)

---

## API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register/` | Create account |
| `POST` | `/api/auth/login/` | Login → JWT tokens |
| `POST` | `/api/auth/token/refresh/` | Refresh access token |
| `POST` | `/api/auth/logout/` | Blacklist refresh token |

### Repositories
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/repositories/` | List your repos |
| `POST` | `/api/repositories/` | Register a repo |
| `GET` | `/api/repositories/{id}/` | Repo detail |
| `DELETE` | `/api/repositories/{id}/` | Soft delete |
| `POST` | `/api/repositories/{id}/rotate-secret/` | New webhook secret |
| `GET` | `/api/repositories/{id}/stats/` | Review statistics |
| `GET` | `/api/repositories/{id}/reviews/` | All reviews for repo |

### Reviews
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/reviews/` | All reviews (with filters) |
| `GET` | `/api/reviews/{id}/` | Review detail + issues |
| `GET` | `/api/reviews/{id}/issues/` | Just the issues |
| `POST` | `/api/reviews/{id}/retry/` | Retry failed review |

**Filter reviews:**
```
GET /api/reviews/?repo=my-repo
GET /api/reviews/?pr_number=42
GET /api/reviews/?severity=critical
```

### Webhook
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/webhooks/github/` | GitHub webhook receiver |
| `GET` | `/api/webhooks/events/` | Inspect received events |

Full interactive docs: `http://localhost:8000/api/docs/`

---

## Testing

```bash
# Run all 66 tests
pytest

# With coverage report
pytest --cov=apps --cov-report=term-missing

# Run one file
pytest tests/test_ai_review.py -v
```

**Coverage: 79%** across 66 tests

| Test File | What It Covers |
|-----------|----------------|
| `test_webhook_signature.py` | HMAC verification — 7 edge cases including timing attack prevention |
| `test_webhook_receiver.py` | Full webhook flow with mocked Celery |
| `test_auth.py` | Register, login, logout, token refresh |
| `test_repositories.py` | CRUD, soft delete, secret rotation, ownership isolation |
| `test_ai_review.py` | File filtering, prompt building, response parsing |
| `test_review_api.py` | List/filter/retry, cross-user isolation |
| `test_celery_tasks.py` | Task chain, error handling, retry logic |

---

## Challenges Faced

### 1. `request.body` after `request.data` crash

Django's request object reads the body stream once. If you access `request.data` first (which DRF does automatically for JSON parsing), `request.body` becomes empty. This caused HMAC verification to silently fail on every webhook.

**Fix:** Read `request.body` as the very first line of the webhook view, before any access to `request.data`. Documented in code with a comment so nobody "fixes" it later.

### 2. Webhook secrets — hash vs encrypt

First implementation stored SHA-256 hash of the webhook secret. Looked secure. Problem: HMAC verification needs the **plain secret**, not the hash. You can't reverse a hash. So verification always failed.

**Fix:** Switched to Fernet symmetric encryption. Store ciphertext, decrypt at verification time. Encryption key lives in env var — separate from the encrypted data. Even if someone gets the database, they can't recover secrets without the key.

### 3. Groq model deprecation mid-development

`llama3-8b-8192` was decommissioned while building this. Every API call started returning 400. No warning, no grace period.

**Fix:** Updated to `llama-3.1-8b-instant`. Also switched from Groq SDK to direct `requests.post()` to avoid SDK version conflicts — HTTP APIs don't deprecate.

### 4. AI returning markdown instead of JSON

The system prompt says "return ONLY valid JSON". The AI still occasionally wraps it in ` ```json ``` ` markdown fences. `json.loads()` on that throws an exception.

**Fix:** `parse_ai_response()` strips markdown fences before parsing. If parsing still fails, it returns a safe default (score=0, approved=False) instead of crashing the task.

### 5. Celery task chain — how to pass data between tasks

Task 2 needs the `pr_diff_id` from Task 1's DB write. Task 3 needs `pr_diff_id` too. Celery's built-in chaining (`chain()`) passes return values automatically, but you lose error isolation — one task's failure cascades.

**Fix:** Each task explicitly queries the DB for what it needs, stores results, then calls the next task with `.delay()`. More DB queries, but tasks are fully independent. Task 3 can be re-run standalone without re-running Task 1 and 2. This matters for the retry endpoint.

### 6. Factory-boy and password hashing in tests

`UserFactory` with `PostGenerationMethodCall('set_password', ...)` hashes the password after creation — but Django doesn't re-save the instance automatically after post-generation hooks in newer versions. Every test login returned 401.

**Fix:** Override `_after_postgeneration()` in `UserFactory` to call `instance.save()` after the password is set. Simple, but took an hour to trace.

---

## Project Structure

```
code_review_bot/
├── config/
│   ├── settings/
│   │   ├── base.py          # All shared settings
│   │   ├── development.py   # Local dev overrides
│   │   └── production.py    # Production + security headers
│   ├── celery.py            # Celery app + autodiscover
│   └── urls.py              # Root URL router
│
├── apps/
│   ├── core/                # TimeStampedModel, middleware, exceptions
│   ├── users/               # CustomUser + JWT auth endpoints
│   ├── repositories/        # GitHub repo registration + secret management
│   ├── webhooks/            # Webhook receiver, HMAC verification, Task 1
│   └── reviews/             # Diff fetching (Task 2), AI review (Task 3), REST API
│
├── tests/
│   ├── factories.py         # Test data factories
│   └── test_*.py            # 66 tests across 7 files
│
├── Dockerfile
├── docker-compose.yml
├── render.yaml              # Render deployment
├── .github/workflows/ci.yml # GitHub Actions
└── requirements.txt
```

---

## Deployment (Render)

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your repo — Render reads `render.yaml` automatically
4. Add three env vars manually in Render dashboard:
   - `GROQ_API_KEY`
   - `GITHUB_TOKEN`
   - `WEBHOOK_SECRET_ENCRYPTION_KEY`
5. Deploy

Render creates: Django web service + Celery worker + Celery beat + PostgreSQL + Redis.

---

## Scoring Logic

```
Score 90–100  → Excellent → Auto-approved ✅
Score 75–89   → Good, minor issues → Approved ✅
Score 50–74   → Needs work → Not approved ❌
Score 0–49    → Critical issues → Blocked ❌

approved = true  only if  score >= 75
```

---

<div align="center">

Built by **Sumit Shukla**

*The bot reviews code faster than I can open the PR tab.*

[GitHub](https://github.com/Sumitshukla7318) · [Swagger Docs](http://localhost:8000/api/docs/)

</div>