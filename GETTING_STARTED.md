# Lumina — Getting Started (Complete Beginner's Guide)

This guide walks you through everything from zero to a running Lumina instance.
No prior experience with Docker, PostgreSQL, or Python is assumed.

---

## Table of Contents

1. [What You Need (Prerequisites)](#1-what-you-need-prerequisites)
2. [Install the Prerequisites](#2-install-the-prerequisites)
3. [Get an AI API Key](#3-get-an-ai-api-key)
4. [Download / Clone the Project](#4-download--clone-the-project)
5. [Configure Environment Variables (.env)](#5-configure-environment-variables-env)
6. [Start the App with Docker Compose](#6-start-the-app-with-docker-compose)
7. [Set Up the Database (first run only)](#7-set-up-the-database-first-run-only)
8. [Open the App](#8-open-the-app)
9. [Stopping and Restarting](#9-stopping-and-restarting)
10. [Local Development (without Docker)](#10-local-development-without-docker)
11. [Common Errors and Fixes](#11-common-errors-and-fixes)
12. [Full .env Reference](#12-full-env-reference)
13. [Phase 2 Roadmap](#13-phase-2-roadmap)

---

## 1. What You Need (Prerequisites)

You need three things installed on your computer before starting:

| Tool | What it is | Why Lumina needs it |
|------|-----------|---------------------|
| **Docker Desktop** | Runs apps in isolated containers | Runs PostgreSQL, Redis, and the backend without manual installs |
| **Node.js 22+** | JavaScript runtime | Runs the Next.js frontend during development |
| **Git** | Version control | Downloads the project code |

You also need an account at **OpenAI** (or Anthropic) to get an API key.

---

## 2. Install the Prerequisites

### Docker Desktop

Docker lets you run PostgreSQL, Redis, and the Python backend without installing them
directly on your machine. Everything runs inside containers.

**macOS:**
1. Go to [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Click **"Download for Mac"** (choose Apple Silicon if you have an M1/M2/M3 chip, Intel otherwise)
3. Open the downloaded `.dmg` file and drag Docker to your Applications folder
4. Open Docker from Applications — a whale icon appears in your menu bar
5. Wait until the menu bar icon stops animating (Docker is ready)

**Windows:**
1. Go to [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Click **"Download for Windows"**
3. Run the installer (requires Windows 10/11 with WSL 2 enabled)
4. Restart your computer if prompted
5. Open Docker Desktop from the Start menu

**Verify Docker is working** — open a terminal and run:
```bash
docker --version
# Should print something like: Docker version 27.x.x
```

---

### Node.js 22+

**macOS / Linux (recommended — uses nvm to manage Node versions):**
```bash
# Install nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Restart your terminal, then install Node 22
nvm install 22
nvm use 22
```

**Windows:**
1. Go to [https://nodejs.org](https://nodejs.org)
2. Download the **LTS** version (22.x)
3. Run the installer, click through the defaults

**Verify:**
```bash
node --version
# Should print: v22.x.x

npm --version
# Should print: 10.x.x
```

---

### Git

**macOS:** Git is usually already installed. Check with:
```bash
git --version
```
If not found, macOS will prompt you to install Xcode Command Line Tools — click Install.

**Windows:** Download from [https://git-scm.com/download/win](https://git-scm.com/download/win) and run the installer.

---

## 3. Get an AI API Key

Lumina uses OpenAI (default) or Anthropic to power the AI. You need at least one key.

### OpenAI (recommended for beginners)

1. Go to [https://platform.openai.com](https://platform.openai.com) and create an account
2. Click your profile icon (top right) → **"API keys"**
3. Click **"Create new secret key"**, give it a name like "Lumina"
4. **Copy the key immediately** — it starts with `sk-` and you cannot see it again after closing the dialog
5. Add a payment method under **Billing** (OpenAI charges per use; for development, $5 credit goes a long way)

### Anthropic (alternative)

1. Go to [https://console.anthropic.com](https://console.anthropic.com) and create an account
2. Go to **"API Keys"** in the left sidebar
3. Click **"Create Key"**, copy the key (starts with `sk-ant-`)
4. Add a payment method under **Billing**

> **Which to choose?** OpenAI's `gpt-4o` is the default model and works great.
> You can configure Anthropic's Claude as well — or both at the same time.

---

## 4. Download / Clone the Project

Open a terminal (Terminal on macOS, Command Prompt or PowerShell on Windows):

```bash
# Navigate to where you want the project to live, e.g. your home folder
cd ~

# Clone the repository (downloads all the code)
git clone <your-repo-url> lumina

# Enter the project folder
cd lumina
```

You should now have a `lumina/` folder with `backend/`, `frontend/`, and `docker-compose.yml` inside.

---

## 5. Configure Environment Variables (.env)

Environment variables are settings your app reads at startup — things like API keys,
database passwords, and feature flags. They live in `.env` files so they're never
committed to version control.

### Step 1 — Create the backend .env file

```bash
# From the lumina/ root folder
cp backend/.env.example backend/.env
```

Now open `backend/.env` in any text editor (VS Code, Notepad, etc.).

### Step 2 — Generate a secret key

The `APP_SECRET_KEY` is used to sign login tokens. Generate a random one:

```bash
# Run this in your terminal — copy the output
python3 -c "import secrets; print(secrets.token_hex(32))"
```

This prints a string like `a3f8b2c1d4e5f6...`. Paste it as the value for `APP_SECRET_KEY`.

> **Windows users:** If `python3` is not found, try `python` instead.
> If Python isn't installed, go to [https://python.org](https://python.org) and install it.

### Step 3 — Fill in backend/.env

Here is every variable explained. Required ones are marked with ⚠️.

```env
# ── App ──────────────────────────────────────────────────────────
# ⚠️ REQUIRED — paste the random string you generated above
APP_SECRET_KEY=paste_your_generated_secret_here

# Leave as "development" while building/testing
APP_ENV=development

# Controls debug output. True = more logs (good for development)
APP_DEBUG=true


# ── Database ─────────────────────────────────────────────────────
# ⚠️ REQUIRED — tells the backend how to connect to PostgreSQL
# When using Docker Compose: use this exact value (matches docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://lumina:lumina_pass@db:5432/lumina_db

# If running locally (not Docker): replace "db" with "localhost"
# DATABASE_URL=postgresql+asyncpg://lumina:lumina_pass@localhost:5432/lumina_db


# ── Redis ────────────────────────────────────────────────────────
# ⚠️ REQUIRED — tells the backend where Redis is
# When using Docker Compose: use this exact value
REDIS_URL=redis://redis:6379/0

# If running locally: replace "redis" with "localhost"
# REDIS_URL=redis://localhost:6379/0


# ── AI Providers ─────────────────────────────────────────────────
# Which AI to use by default: "openai" or "anthropic"
DEFAULT_AI_PROVIDER=openai

# ⚠️ REQUIRED if DEFAULT_AI_PROVIDER=openai
# Your OpenAI API key (starts with sk-)
OPENAI_API_KEY=sk-your-key-here

# Optional — your OpenAI organization ID (leave blank if you don't have one)
OPENAI_ORG_ID=

# Which OpenAI model to use for chat (gpt-4o is the best, gpt-4o-mini is cheaper)
DEFAULT_CHAT_MODEL=gpt-4o

# Faster/cheaper model used for background tasks (title generation, etc.)
DEFAULT_FAST_MODEL=gpt-4o-mini

# Model used to generate embeddings for RAG (document search)
DEFAULT_EMBED_MODEL=text-embedding-3-small


# ⚠️ REQUIRED if DEFAULT_AI_PROVIDER=anthropic
# Your Anthropic API key (starts with sk-ant-)
ANTHROPIC_API_KEY=

# Which Claude model to use
DEFAULT_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022


# ── Celery (background task queue) ───────────────────────────────
# These use Redis as the broker. Match the REDIS_URL host above.
# Docker Compose: use "redis" as the hostname
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Local development: use "localhost"
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/2


# ── CORS (which frontend URLs are allowed to talk to the backend) ─
# During development, the frontend runs on port 3000
ALLOWED_ORIGINS=["http://localhost:3000"]


# ── File Uploads (for RAG document search) ───────────────────────
# Max upload file size in megabytes
MAX_FILE_SIZE_MB=25

# Where to store uploaded files (relative to where the backend runs)
# In Docker this becomes /app/uploads inside the container
LOCAL_STORAGE_PATH=./uploads


# ── Feature Flags ─────────────────────────────────────────────────
# Enable/disable tool calling (calculator, weather, web search)
TOOLS_ENABLED=true
TOOLS_MAX_ROUNDS=5

# Enable automatic memory extraction from conversations
MEMORY_EXTRACTION_ENABLED=true


# ── Rate Limiting ─────────────────────────────────────────────────
# Max chat messages per user per minute
RATE_LIMIT_CHAT_PER_MINUTE=30

# Max general API calls per user per minute
RATE_LIMIT_API_PER_MINUTE=100


# ── Logging ───────────────────────────────────────────────────────
LOG_LEVEL=INFO
# "json" for production, "pretty" for development (easier to read)
LOG_FORMAT=pretty
```

### Step 4 — Create the frontend .env file

```bash
cp frontend/.env.local.example frontend/.env.local
```

Open `frontend/.env.local`. It usually only needs one variable:

```env
# The URL your frontend uses to talk to the backend API
# During Docker Compose development, use this:
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **What is NEXT_PUBLIC?** Variables starting with `NEXT_PUBLIC_` are exposed to
> the browser. Other variables stay server-side only.

---

## 6. Start the App with Docker Compose

Docker Compose reads `docker-compose.yml` and starts all services together:
PostgreSQL (database), Redis (cache/queue), the FastAPI backend, the Celery worker,
and the Next.js frontend.

```bash
# Make sure you're in the lumina/ root folder
cd ~/lumina

# Start all services (downloads images on first run — may take 5-10 minutes)
docker compose up
```

You'll see logs from all services scrolling by. Wait until you see something like:
```
backend  | INFO: Application startup complete.
frontend | ✓ Ready in 2.3s
```

> **First run takes longer** because Docker downloads the base images (Python, Node, PostgreSQL, Redis).
> Subsequent starts are much faster.

**Run in the background** (so you can keep using the terminal):
```bash
docker compose up -d
# -d means "detached" — runs in the background
# View logs any time with: docker compose logs -f
```

---

## 7. Set Up the Database (first run only)

The database tables need to be created before the app works. Do this **once** after
the first `docker compose up`:

```bash
# Open a new terminal tab, navigate to lumina/

# Run the database migrations (creates all tables)
docker compose exec backend alembic upgrade head

# Set up the pgvector extension and document tables (for RAG / file upload)
docker compose exec backend psql $DATABASE_URL -f migrations/add_document_tables.sql
```

> **What is a migration?** It's a script that creates or modifies database tables.
> `alembic upgrade head` runs all pending migrations in order.
> You only need to do this once (unless you update the code and there are new migrations).

### Verify the database is set up

```bash
# Connect to the database and list tables
docker compose exec db psql -U lumina -d lumina_db -c "\dt"
```

You should see a list of tables including `users`, `conversations`, `messages`,
`memory_entries`, `documents`, etc.

---

## 8. Open the App

Once everything is running:

| Service | URL | Notes |
|---------|-----|-------|
| **Frontend** | [http://localhost:3000](http://localhost:3000) | The main UI |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | REST API |
| **API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI (dev only) |

1. Open [http://localhost:3000](http://localhost:3000)
2. Click **"Sign Up"** to create your first account
3. Start chatting!

---

## 9. Stopping and Restarting

```bash
# Stop all running containers (keeps data)
docker compose down

# Start again
docker compose up

# Stop AND delete all data (database, Redis cache)
# Use this if you want a completely clean start
docker compose down -v
```

> **Important:** `docker compose down -v` deletes the database. You will lose all
> conversations, users, and uploaded files. Only use it if you want to start fresh.

---

## 10. Local Development (without Docker)

Use this approach if you want to edit code and see changes instantly with hot reload.
You still use Docker for the database and Redis.

### Start PostgreSQL and Redis with Docker

```bash
# PostgreSQL with pgvector support (required for document search)
docker run -d \
  --name lumina_pg \
  -p 5432:5432 \
  -e POSTGRES_USER=lumina \
  -e POSTGRES_PASSWORD=lumina_pass \
  -e POSTGRES_DB=lumina_db \
  pgvector/pgvector:pg16

# Redis
docker run -d \
  --name lumina_redis \
  -p 6379:6379 \
  redis:7-alpine
```

Verify they're running:
```bash
docker ps
# You should see lumina_pg and lumina_redis in the list
```

### Backend (Python / FastAPI)

```bash
cd ~/lumina/backend

# Install uv — a fast Python package manager (much faster than pip)
pip install uv

# Create a virtual environment and install all dependencies
uv venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

uv pip install -e ".[dev]"

# Update backend/.env to use localhost instead of Docker hostnames
# Change: DATABASE_URL=postgresql+asyncpg://lumina:lumina_pass@db:5432/lumina_db
# To:     DATABASE_URL=postgresql+asyncpg://lumina:lumina_pass@localhost:5432/lumina_db
# Same for REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Run database migrations
alembic upgrade head

# Set up document tables
psql postgresql://lumina:lumina_pass@localhost:5432/lumina_db \
  -f migrations/add_document_tables.sql

# Start the backend API server
uvicorn app.main:app --reload --port 8000
# --reload means it restarts automatically when you change code
```

### Celery Worker (background tasks)

Open a **new terminal tab**:

```bash
cd ~/lumina/backend
source .venv/bin/activate

celery -A app.workers.celery_app worker --loglevel=info
```

The Celery worker handles background tasks like:
- Generating conversation titles
- Extracting long-term memories
- Indexing uploaded documents for search

### Frontend (Next.js)

Open another **new terminal tab**:

```bash
cd ~/lumina/frontend

# Install JavaScript dependencies
npm install

# Start the development server
npm run dev

# Open http://localhost:3000
```

The frontend auto-reloads when you edit any file in `src/`.

---

## 11. Common Errors and Fixes

### "Cannot connect to the Docker daemon"
Docker Desktop isn't running. Open it from your Applications folder and wait for the
whale icon in the menu bar to stop animating.

---

### "connection refused" / backend can't reach database
Your `DATABASE_URL` hostname is wrong for your setup:
- **Docker Compose:** use `db` as hostname → `postgresql+asyncpg://lumina:lumina_pass@db:5432/lumina_db`
- **Local dev:** use `localhost` → `postgresql+asyncpg://lumina:lumina_pass@localhost:5432/lumina_db`

---

### "OPENAI_API_KEY is required" on startup
You haven't set the key in `backend/.env`. Double-check the file has:
```env
OPENAI_API_KEY=sk-your-actual-key
```
There should be no quotes around the key value.

---

### Frontend shows unstyled HTML (no CSS)
The PostCSS config was missing. It has been fixed — restart the dev server:
```bash
cd frontend
npm run dev
```

---

### "relation does not exist" database error
The migrations haven't been run. Run:
```bash
docker compose exec backend alembic upgrade head
```

---

### "port already in use"
Another app is using port 3000, 8000, 5432, or 6379. Either:
- Stop the other app
- Or change the port in `docker-compose.yml`

---

### Celery tasks not running (titles not generating, no memory extraction)
The Celery worker isn't started. In Docker Compose it starts automatically.
In local dev, you need to start it manually in a separate terminal (see section 10).

---

### "vector type does not exist" error
The pgvector extension isn't installed in the database. Run:
```bash
docker compose exec db psql -U lumina -d lumina_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
Then re-run the document tables migration.

---

## 12. Full .env Reference

### backend/.env — complete list

```env
# ─── App ──────────────────────────────────────────────────────────────────────
APP_NAME=Lumina AI
APP_ENV=development          # development | staging | production
APP_DEBUG=true               # true = verbose logs
APP_SECRET_KEY=              # ⚠️ REQUIRED — 32+ random chars (generate with python)
APP_VERSION=0.1.0

# ─── Server ───────────────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
WORKERS=1                    # Number of uvicorn workers (increase in production)

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=                # ⚠️ REQUIRED — see section 5 for correct value
DATABASE_POOL_SIZE=20        # Max simultaneous DB connections
DATABASE_MAX_OVERFLOW=10     # Extra connections above pool_size under load
DATABASE_POOL_TIMEOUT=30     # Seconds to wait for a free connection

# ─── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL=                   # ⚠️ REQUIRED — see section 5 for correct value
REDIS_CACHE_TTL=3600         # How long cached data lives (seconds)

# ─── Auth ─────────────────────────────────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=15    # JWT access tokens expire after this
REFRESH_TOKEN_EXPIRE_DAYS=7       # Refresh tokens expire after this
JWT_ALGORITHM=HS256

# ─── CORS ─────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS=["http://localhost:3000"]   # Add your frontend URL here

# ─── AI Providers ─────────────────────────────────────────────────────────────
DEFAULT_AI_PROVIDER=openai         # openai | anthropic | groq
OPENAI_API_KEY=                    # ⚠️ Required if DEFAULT_AI_PROVIDER=openai
OPENAI_ORG_ID=                     # Optional OpenAI org ID
DEFAULT_CHAT_MODEL=gpt-4o          # Main model for conversations
DEFAULT_FAST_MODEL=gpt-4o-mini     # Cheaper model for background tasks
DEFAULT_EMBED_MODEL=text-embedding-3-small   # Used for document search (RAG)
ANTHROPIC_API_KEY=                 # ⚠️ Required if DEFAULT_AI_PROVIDER=anthropic
DEFAULT_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
GROQ_API_KEY=                      # Required if DEFAULT_AI_PROVIDER=groq

# ─── AI Behavior ──────────────────────────────────────────────────────────────
MAX_CONTEXT_TOKENS=128000          # Max tokens in one request to the AI
CONTEXT_RESERVE_TOKENS=2000        # Reserve this many tokens for the AI's response
SUMMARY_TRIGGER_MESSAGES=30        # Summarize conversation after this many messages
MEMORY_EXTRACTION_ENABLED=true     # Auto-extract facts from conversations

# ─── Tools ────────────────────────────────────────────────────────────────────
TOOLS_ENABLED=true                 # Enable calculator, weather, web search tools
TOOLS_MAX_ROUNDS=5                 # Max tool-calling rounds per message

# ─── Rate Limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_CHAT_PER_MINUTE=30      # Max chat messages per user per minute
RATE_LIMIT_API_PER_MINUTE=100      # Max other API calls per user per minute

# ─── File Uploads (RAG) ───────────────────────────────────────────────────────
MAX_FILE_SIZE_MB=25                # Max upload size
ALLOWED_FILE_TYPES=["application/pdf","text/plain","text/markdown"]
STORAGE_BACKEND=local              # local | s3
LOCAL_STORAGE_PATH=./uploads       # Where uploaded files are saved

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL=                 # ⚠️ REQUIRED — see section 5 for correct value
CELERY_RESULT_BACKEND=             # ⚠️ REQUIRED — see section 5 for correct value

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO                     # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=pretty                  # pretty (dev) | json (production)
```

### frontend/.env.local — complete list

```env
# URL of your backend API
# Docker Compose: http://localhost:8000
# Production: https://api.yourdomain.com
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 13. Phase 2 Roadmap

All Phase 2 features are implemented:

- [x] Tool calling (weather, web search, calculator)
- [x] RAG: file upload + chunking + vector search
- [x] Rate limiting (Redis sliding window)
- [x] Model selector in UI
- [x] Persona/assistant mode switching
- [x] Export conversations
- [x] Long-term memory UI (view/delete)

## 14. Phase 3 — Completed

All Phase 3 features are implemented:

- [x] Multi-provider support (Gemini, Groq) — `backend/app/ai/providers/gemini_provider.py`, `groq_provider.py`
- [x] Team/org multi-tenancy — `backend/app/api/v1/organizations.py`, `backend/app/models/organization.py`
- [x] Usage dashboard + billing hooks — `backend/app/api/v1/usage.py`, `frontend/src/app/(chat)/usage/page.tsx`
- [x] Voice (STT/TTS) — `backend/app/api/v1/voice.py`, `frontend/src/hooks/useVoice.ts`
- [x] Agent workflows (planner/executor) — `backend/app/api/v1/agents.py`, `frontend/src/app/(chat)/agents/page.tsx`
- [x] Share conversation links — `backend/app/api/v1/share.py`, `frontend/src/app/share/[token]/page.tsx`
- [x] Admin panel — `backend/app/api/v1/admin.py`, `frontend/src/app/(chat)/admin/page.tsx`

### Phase 3 Database Migrations

Run these after your Phase 1 & 2 migrations:

```bash
# Share links columns
psql $DATABASE_URL -f backend/migrations/phase3_share_links.sql

# Organizations tables
psql $DATABASE_URL -f backend/migrations/phase3_organizations.sql
```

### Phase 3 Environment Variables

Add to `backend/.env`:

```env
# ─── Groq ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...          # get from console.groq.com
GROQ_DEFAULT_MODEL=llama-3.1-8b-instant

# ─── Gemini ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY=AIza...        # get from aistudio.google.com
GEMINI_DEFAULT_MODEL=gemini-2.0-flash
GEMINI_EMBED_MODEL=text-embedding-004

# ─── Voice (requires OpenAI key) ──────────────────────────────────────────────
VOICE_STT_MODEL=whisper-1
VOICE_TTS_MODEL=tts-1
VOICE_TTS_VOICE=alloy         # alloy | echo | fable | onyx | nova | shimmer
```

---

## Adding a New AI Provider

1. Create `backend/app/ai/providers/your_provider.py`
2. Inherit from `BaseAIProvider` (`backend/app/ai/providers/base.py`)
3. Implement: `chat_completion`, `stream_completion`, `generate_embeddings`
4. Register in `backend/app/ai/providers/router.py`
5. Add your API key to `backend/.env` and `backend/app/core/config.py`
