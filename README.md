<div align="center">

# 🧠 RAGDesk

### *The production-ready backend engine for Retrieval-Augmented Generation — built for teams who take their data seriously.*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.133-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.6-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Instrumented-F5A800?style=for-the-badge&logo=opentelemetry&logoColor=black)](https://opentelemetry.io/)
[![License](https://img.shields.io/github/license/mhaiderzeshan/ragdesk?style=for-the-badge)](./LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/mhaiderzeshan/ragdesk?style=for-the-badge)](https://github.com/mhaiderzeshan/ragdesk/commits/main)
[![Repo Size](https://img.shields.io/github/repo-size/mhaiderzeshan/ragdesk?style=for-the-badge)](https://github.com/mhaiderzeshan/ragdesk)

</div>

---

## 📖 Table of Contents

- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Architecture Overview](#-architecture-overview)
- [Built With](#-built-with)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Environment Variables](#-environment-variables)
- [API Endpoints](#-api-endpoints)
- [Folder Structure](#-folder-structure)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

---

## 🎯 About the Project

> **"Your organization generates knowledge every day. RAGDesk makes it queryable."**

Most AI chat applications are bolted on top of generic language models — they're impressive demos, but they don't *know* your business. RAGDesk was built to close that gap.

RAGDesk is a **production-grade, multi-tenant Retrieval-Augmented Generation backend**. It provides the infrastructure to:

1. **Ingest** private documents (PDFs, etc.) asynchronously without blocking your users.
2. **Embed** that content into a high-performance vector store backed by PostgreSQL.
3. **Query** across that knowledge with semantic search — returning not just an AI-generated answer, but the precise **source citations** that grounded it.
4. **Isolate** all of this per-organization (`org_id`), so your multi-tenant SaaS, enterprise app, or internal tool never bleeds data between workspaces.

The result is a clean, well-documented REST API that any developer can deploy in minutes and build a full-featured AI product on top of — without being an ML engineer.


---

## ✨ Key Features

- 🔄 **Async Document Ingestion** — Upload PDFs and walk away. Celery workers handle parsing (PyMuPDF), chunking, and embedding in the background. Poll a status endpoint to track progress.

- 🔍 **Semantic Vector Search** — Using native `pgvector` operators directly inside PostgreSQL, RAGDesk performs fast cosine-similarity search over dense embeddings with no separate vector database to maintain.

- 🏢 **Multi-Tenant by Design** — Every knowledge base, document, chunk, and chat history is scoped to an `org_id`. Tenant isolation is enforced at the query layer — not just the application layer.

- 💬 **Streaming Chat with Citations** — The chat API supports both standard JSON responses and **Server-Sent Events (SSE) streaming**, delivering tokens in real-time while appending source citations in the final event.

- 🔐 **Secure & Observable** — JWT authentication (Argon2 password hashing), RBAC middleware, rate limiting (20 req/min per endpoint), and full **OpenTelemetry** tracing across the API and database layers.

---

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Client / UI                         │
│             (Nginx · Port 5500 · Static Frontend)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / SSE
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI REST API                        │
│         (Uvicorn · Port 8000 · Async · Rate Limited)        │
│    /auth  /documents  /knowledgebases  /chat  /eval         │
└───────────┬─────────────────────────────┬───────────────────┘
            │ SQLAlchemy (asyncpg)         │ Task dispatch
            ▼                             ▼
┌───────────────────────┐   ┌─────────────────────────────────┐
│  PostgreSQL + pgvector │   │       Redis (Broker/Cache)      │
│  · Relational tables  │   └──────────────┬──────────────────┘
│  · Vector embeddings  │                  │ Celery tasks
└───────────────────────┘                  ▼
                              ┌─────────────────────────┐
                              │      Celery Worker       │
                              │  · PDF parse (PyMuPDF)   │
                              │  · Chunk & embed (OpenAI)│
                              │  · Write vectors to DB   │
                              └─────────────────────────┘
```

---

## 🛠 Built With

| Layer | Technology | Purpose |
|---|---|---|
| **API** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance async REST framework |
| **Server** | [Uvicorn](https://www.uvicorn.org/) | ASGI server |
| **Database** | [PostgreSQL 16](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) | Relational data + vector similarity search |
| **ORM** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/) | Async ORM + schema migrations |
| **Queue** | [Celery](https://docs.celeryq.dev/) + [Redis](https://redis.io/) | Background task processing |
| **AI / Embeddings** | [OpenAI API](https://platform.openai.com/) / [Google Generative AI](https://ai.google.dev/) | LLM inference + embedding generation |
| **PDF Parsing** | [PyMuPDF](https://pymupdf.readthedocs.io/) | Fast, accurate document extraction |
| **Auth** | [PyJWT](https://pyjwt.readthedocs.io/) + [pwdlib (Argon2)](https://github.com/frankie567/pwdlib) | Token auth + secure password hashing |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Schema validation + settings management |
| **Observability** | [OpenTelemetry](https://opentelemetry.io/) | Distributed tracing (FastAPI + SQLAlchemy) |
| **Rate Limiting** | [SlowAPI](https://github.com/laurentS/slowapi) | Per-endpoint request throttling |
| **Infrastructure** | [Docker](https://www.docker.com/) + [Docker Compose](https://docs.docker.com/compose/) | Containerized, reproducible deployments |
| **Frontend** | [Nginx](https://nginx.org/) | Static file serving |

---

## ⚡ Quick Start

> **Estimated time to a running API: ~3 minutes.**

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and an [OpenAI API key](https://platform.openai.com/api-keys).

```bash
# 1. Clone the repository
git clone https://github.com/mhaiderzeshan/ragdesk.git && cd ragdesk

# 2. Configure your environment
cp .env.example .env
# → Open .env and fill in your OPENAI_API_KEY, DB_PASSWORD, etc.

# 3. Spin up the entire stack
docker-compose up -d --build

# 4. Verify everything is healthy
curl http://localhost:8000/health
# → {"status": "ok"}
```

The interactive API docs are live at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

---

## 🚀 Installation

### Prerequisites

Ensure the following are installed on your machine:

- [Git](https://git-scm.com/)
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- An **OpenAI API Key** (or valid Google Generative AI credentials)

### Step-by-Step Setup

**1. Clone the repository**

```bash
git clone https://github.com/mhaiderzeshan/ragdesk.git
cd ragdesk
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the required values (see [Environment Variables](#-environment-variables) below).

**3. Build and launch the stack**

```bash
docker-compose up -d --build
```

This single command provisions and starts:
- `ragdesk_db` — PostgreSQL 16 with the `pgvector` extension auto-enabled
- `ragdesk_redis` — Redis 7 message broker
- `ragdesk_api` — FastAPI application on port `8000`
- `ragdesk_worker` — Celery background worker
- `ragdesk_frontend` — Nginx static file server on port `5500`

**4. Run database migrations (optional — tables auto-create on startup)**

```bash
docker-compose exec api alembic upgrade head
```

**5. Verify the deployment**

| Service | URL |
|---|---|
| REST API | https://api-service-production-46be.up.railway.app |
| Swagger UI | https://api-service-production-46be.up.railway.app/docs|
| ReDoc | https://api-service-production-46be.up.railway.app/redoc|
| Frontend | https://ragdesk-production.up.railway.app/|

---

## 🔑 Environment Variables

Create a `.env` file in the project root. The following variables are required:

```env
# ── Database ─────────────────────────────────────────────────
DB_USER=ragdesk_user
DB_PASSWORD=your_secure_password
DB_NAME=ragdesk_db

# ── AI / Embeddings ───────────────────────────────────────────
OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=...   ← Alternative if using Google Generative AI

# ── Security ──────────────────────────────────────────────────
SECRET_KEY=your_jwt_secret_key_change_in_production
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Redis ─────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
```


---

## 📡 API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/auth/register` | Register a new user | ❌ |
| `POST` | `/auth/login` | Obtain a JWT access token | ❌ |
| `GET` | `/health` | Health check | ❌ |
| `POST` | `/knowledgebases` | Create a new knowledge base | ✅ |
| `GET` | `/knowledgebases` | List all org knowledge bases | ✅ |
| `POST` | `/documents/upload` | Upload & trigger async ingestion | ✅ |
| `GET` | `/documents/{id}/status` | Poll document ingestion status | ✅ |
| `POST` | `/chat` | Non-streaming RAG answer with citations | ✅ |
| `POST` | `/chat/stream` | SSE streaming answer with citations | ✅ |
| `GET` | `/chats/{id}` | Retrieve conversation history | ✅ |
| `POST` | `/feedback` | Submit response feedback | ✅ |
| `GET` | `/eval` | Retrieve evaluation metrics | ✅ |


Full interactive documentation is available at `/docs` once the server is running.

---

## 📁 Folder Structure

```
ragdesk/
├── app/
│   ├── api/
│   │   ├── deps.py              # Auth dependency injection
│   │   ├── rbac.py              # Role-Based Access Control
│   │   └── endpoints/
│   │       ├── auth.py          # Registration & login
│   │       ├── knowledgebase.py # KB CRUD (multi-tenant scoped)
│   │       ├── document.py      # Upload & ingestion status polling
│   │       ├── chat.py          # RAG chat (standard + streaming)
│   │       ├── feedback.py      # User response feedback
│   │       └── eval.py          # RAG evaluation metrics
│   ├── core/
│   │   ├── logging.py           # Structured JSON logging
│   │   └── rate_limit.py        # SlowAPI rate limiter config
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic v2 request/response schemas
│   ├── services/                # Business logic (chat, audit, etc.)
│   ├── repositories/            # Data access layer
│   ├── workers/
│   │   ├── celery_app.py        # Celery app configuration
│   │   └── tasks.py             # Async ingestion task (parse → chunk → embed)
│   ├── db.py                    # Async SQLAlchemy engine + session
│   └── main.py                  # FastAPI app factory, middleware, routers
├── migrations/                  # Alembic migration scripts
├── tests/                       # pytest async test suite
├── frontend/                    # Static files served by Nginx
├── init-db/                     # DB init SQL (pgvector extension)
├── Dockerfile                   # Python 3.11-slim multi-stage image
├── docker-compose.yml           # Full 5-service orchestration
├── requirements.txt             # Pinned Python dependencies
└── .env.example                 # Environment variable template
```

---

## 🗺 Roadmap

- [x] Async document ingestion with Celery
- [x] pgvector semantic search
- [x] Multi-tenant knowledge base isolation
- [x] SSE streaming chat with citations
- [x] JWT authentication + Argon2 hashing
- [x] OpenTelemetry distributed tracing
- [x] Rate limiting
- [x] User feedback collection
- [ ] Webhook notifications on ingestion completion
- [ ] Hybrid search (BM25 + vector) for improved recall
- [ ] Admin dashboard UI for knowledge base management
- [ ] Support for `.docx`, `.csv`, and web URL ingestion
- [ ] Configurable chunking strategies (fixed, sentence, semantic)
- [ ] Multi-model support with switchable embedding providers
- [ ] LangSmith / LangFuse integration for production RAG evaluation

---

## 🤝 Contributing

Contributions are what make open source projects thrive. Any improvement — bug fixes, new features, better documentation — is greatly appreciated.

1. **Fork** the repository
2. **Create** your feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'feat: add amazing feature'`
4. **Push** to your branch: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

Please ensure your code:
- Follows the existing async patterns (use `async def` for I/O-bound operations)
- Includes schema validation via Pydantic models
- Adds or updates tests in the `tests/` directory

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.

---

## 📬 Contact

**M. Haider Zeshan** — [@mhaiderzeshan](https://github.com/mhaiderzeshan)

Project Link: [https://github.com/mhaiderzeshan/ragdesk](https://github.com/mhaiderzeshan/ragdesk)

---

<div align="center">

*Built with ❤️ and a lot of async/await*

⭐ **If RAGDesk saved you time, consider giving it a star!** ⭐

</div>
