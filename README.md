# 🤖 AI Code Review Bot

A production-grade, self-hosted AI-powered code review system built with Django. Automatically reviews GitHub Pull Requests using LLaMA AI and posts structured feedback as PR comments.

> A self-hosted alternative to CodeRabbit / GitHub Copilot Review.

---

## 🏗️ Architecture
```
GitHub PR Opened
      │
      ▼
┌─────────────────┐
│  GitHub Webhook  │  POST /api/webhooks/github/
│  (HMAC verified) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Django API     │  Stores WebhookEvent
│  (DRF + JWT)    │  Returns 200 immediately
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Celery Task 1  │  process_webhook_event()
│  (Redis broker) │  Validates PR action
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Celery Task 2  │  fetch_pr_diff()
│                 │  GitHub API → filter files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Celery Task 3  │  perform_ai_review()
│                 │  Groq API (LLaMA 3.1)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PostgreSQL     │  Stores CodeReview
│                 │  + ReviewIssues
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GitHub PR      │  Posts review as
│  Comment        │  PR comment
└─────────────────┘
```

---

## ✨ Features

- **GitHub Webhook Integration** — Receives PR events with HMAC-SHA256 signature verification
- **Async Processing** — Celery task chain processes diffs without blocking
- **AI Code Review** — LLaMA 3.1 via Groq API analyzes code and returns structured JSON
- **PR Comments** — Posts formatted review directly on GitHub PR
- **REST API** — Query reviews, filter by repo/PR/severity
- **Redis Caching** — Caches review results by commit SHA
- **JWT Auth** — Secure API access with token blacklisting
- **Celery Beat** — Auto-retries stuck reviews, cleans old logs
- **79% Test Coverage** — pytest + factory-boy test suite

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Django 5.x, Django REST Framework |
| Auth | JWT (djangorestframework-simplejwt) |
| Queue | Celery 5.x |
| Broker | Redis 7 |
| Database | PostgreSQL 15 |
| AI | Groq API (LLaMA 3.1 8B — free tier) |
| Docs | drf-spectacular (Swagger) |
| Testing | pytest, factory-boy, responses |
| Deploy | Render (web + worker + beat) |

---

## 📁 Project Structure
```
code_review_bot/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── development.py   # Dev overrides
│   │   └── production.py    # Prod overrides
│   ├── celery.py            # Celery config
│   └── urls.py              # Root URLs
├── apps/
│   ├── core/                # Base models, middleware, exceptions
│   ├── users/               # Custom user + JWT auth
│   ├── repositories/        # GitHub repo registration
│   ├── webhooks/            # Webhook receiver + processing
│   └── reviews/             # AI review engine + REST API
└── tests/                   # Full test suite
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis

### Setup
```bash
# Clone
git clone https://github.com/Sumitshukla7318/code-review-bot.git
cd code-review-bot

# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your values

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add output to WEBHOOK_SECRET_ENCRYPTION_KEY in .env

# Database
createdb code_review_bot
python manage.py migrate

# Run
python manage.py runserver

# Celery worker (new terminal)
celery -A config worker --loglevel=info

# Celery beat (new terminal)
celery -A config beat --loglevel=info
```

### Docker (One Command)
```bash
cp .env.example .env
# Edit .env with your API keys

docker-compose up --build
```

---

## 🔑 Environment Variables
```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/code_review_bot
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=gsk_your_groq_key        # Free at console.groq.com
GITHUB_TOKEN=ghp_your_github_token    # For fetching diffs + posting comments
WEBHOOK_SECRET_ENCRYPTION_KEY=        # Generate with Fernet.generate_key()
DJANGO_SETTINGS_MODULE=config.settings.development
```

---

## 📡 API Endpoints

### Auth
```
POST   /api/auth/register/          Register new user
POST   /api/auth/login/             Login → returns JWT tokens
POST   /api/auth/token/refresh/     Refresh access token
POST   /api/auth/logout/            Blacklist refresh token
```

### Repositories
```
GET    /api/repositories/                    List your repos
POST   /api/repositories/                   Register a repo
GET    /api/repositories/{id}/              Repo detail
PUT    /api/repositories/{id}/              Update repo
DELETE /api/repositories/{id}/              Soft delete
POST   /api/repositories/{id}/rotate-secret/ Rotate webhook secret
GET    /api/repositories/{id}/stats/        Review statistics
GET    /api/repositories/{id}/reviews/      All reviews for repo
```

### Webhooks
```
POST   /api/webhooks/github/        GitHub webhook receiver
GET    /api/webhooks/events/        List webhook events (debug)
GET    /api/webhooks/events/{id}/   Event detail
```

### Reviews
```
GET    /api/reviews/                         List all reviews
GET    /api/reviews/{id}/                    Review detail
GET    /api/reviews/{id}/issues/             Issues for review
POST   /api/reviews/{id}/retry/             Retry failed review

# Filters
GET    /api/reviews/?repo=myrepo
GET    /api/reviews/?pr_number=42
GET    /api/reviews/?severity=critical
```

**Swagger docs:** `http://localhost:8000/api/docs/`

---

## 🔄 How It Works

### 1. Register Your Repository
```bash
curl -X POST http://localhost:8000/api/repositories/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name": "my-repo", "owner": "myusername", "github_url": "..."}'
```

Response includes a `webhook_secret` — save it, shown only once.

### 2. Add Webhook to GitHub
- Go to your repo → Settings → Webhooks → Add webhook
- URL: `https://your-domain.com/api/webhooks/github/`
- Secret: the `webhook_secret` from step 1
- Events: Pull requests

### 3. Open a Pull Request
The system automatically:
1. Receives the webhook
2. Fetches the diff from GitHub API
3. Sends to Groq AI for review
4. Stores structured results
5. Posts review as PR comment

### 4. Query Reviews via API
```bash
curl http://localhost:8000/api/reviews/?repo=my-repo \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🧪 Testing
```bash
# Run all tests
pytest

# With coverage report
pytest --cov=apps --cov-report=html

# Run specific test file
pytest tests/test_ai_review.py -v
```

**Current coverage: 79%**

---

## 🤖 AI Review Format

The AI returns structured JSON which is stored and served via API:
```json
{
  "summary": "This PR adds user authentication with some security concerns.",
  "issues": [
    {
      "file": "views.py",
      "line": 42,
      "severity": "critical",
      "type": "security",
      "message": "SQL injection vulnerability detected",
      "suggestion": "Use parameterized queries instead of string formatting"
    }
  ],
  "score": 45,
  "approved": false
}
```

**Scoring:**
- 90-100: Excellent → Auto approved
- 70-89: Good with minor issues
- 50-69: Needs work
- Below 50: Do not approve

---

## 📊 Repository Statistics
```bash
GET /api/repositories/{id}/stats/
```
```json
{
  "total_reviews": 24,
  "average_score": 72.5,
  "most_common_issue_types": [
    {"issue_type": "style", "count": 18},
    {"issue_type": "security", "count": 7}
  ],
  "files_with_most_issues": [
    {"file_path": "views.py", "count": 12}
  ]
}
```

---

## 🚢 Deploy to Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your repo — Render reads `render.yaml` automatically
4. Add environment variables in Render dashboard:
   - `GROQ_API_KEY`
   - `GITHUB_TOKEN`
   - `WEBHOOK_SECRET_ENCRYPTION_KEY`
5. Deploy

Render will create:
- Django web service
- Celery worker
- Celery beat scheduler
- PostgreSQL database
- Redis instance

---

## 🗄️ Database Models
```
CustomUser          → UUID pk, email login
Repository          → GitHub repo registration, encrypted webhook secret
WebhookEvent        → Full lifecycle tracking (PENDING→PROCESSING→COMPLETED)
PRDiff              → Filtered files sent to AI
CodeReview          → AI review results, score, approval status
ReviewIssue         → Individual issues (file, line, severity, suggestion)
```

---

## 📝 License

MIT License — feel free to use this for your own projects.

---

## 👤 Author

**Sumit Shukla**
- GitHub: [@Sumitshukla7318](https://github.com/Sumitshukla7318)