# RepoMind – Open-Source Project Intelligence & Issue Triage Agent

RepoMind is a centralized web platform designed to simplify exploring open-source GitHub repositories and managing their issues. Built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, and **React 18 + TypeScript + Vite**, RepoMind retrieves repository metadata and issues through the GitHub REST API and organizes them in a relational database with JWT authentication, issue filtering, pagination, and real-time background ingestion tracking.

---

## Evaluation 1 Implementation Status

This repository contains the complete implementation for **Evaluation 1: Core Application Development**, fulfilling all functional and non-functional requirements specified in the Project Requirements Document (PRD):

- **Backend REST APIs**: Developed with FastAPI, mounted under `/api`, fully typed with Pydantic schemas and OpenAPI documentation (`/docs`).
- **PostgreSQL Database Storage**: Relational models for `users`, `repositories`, `issues`, and `ingestion_jobs` (with JSONB labels and comment counts).
- **GitHub Ingestion Engine**: Background asynchronous ingestion fetching repository metadata and up to 3 pages of 100 issues (excluding pull requests) with duplicate-safe synchronization and rate-limit handling.
- **JWT & Argon2 Authentication**: User registration, login with 30-minute bearer tokens, password hashing with Argon2 via `pwdlib`, and protected routes dependency.
- **Repository Management**: Validation and normalization of GitHub URLs and `owner/repo` formats, duplicate rejection (409 Conflict), repository deletion with cascading issues.
- **Issue Exploration & Filtering**: Multi-parameter issue querying by state (`open`/`closed`), label, and title substring with configurable pagination (`page`, `per_page`).
- **React Frontend**: Single-page application built with React 18, TypeScript, and Vite featuring modern dark UI, live job progress polling, issue search, filtering, and issue detail modal.
- **Automated Test Suite**: **37 automated tests passing** across authentication, security, repositories, issues, GitHub client, and ingestion service.

---

## Team Responsibilities & Deliverables (Evaluation 1)

| Member | Role | Evaluation 1 Responsibilities & Deliverables |
|---|---|---|
| **Taniya Tandon** (2410993067) | Backend Development & System Integration Lead | FastAPI architecture, JWT authentication (`/api/auth`), protected endpoints, input validation, error handling, and router integration. |
| **Gourvi** (2410993028) | Database Management & GitHub Integration Engineer | PostgreSQL database schema (`create_tables.py`), SQLAlchemy ORM models, GitHub REST API client (`HTTPX`), duplicate-safe ingestion pipeline, and job status tracking. |
| **Janvi Aggarwal** (2410993200) | Frontend Development & User Interface Engineer | React 18 + TypeScript SPA, user authentication dialogs, repository cards with add/delete/sync, live ingestion polling, issue explorer with filters & pagination, and issue detail modal. |
| **Mohit** (2410993236) | Quality Assurance, Testing & AI/ML Engineer | Automated test suite with **37 passing unit & integration tests**, test database fixtures, and end-to-end workflow verification script (`verify_workflow.py`). |

---

## System Architecture (Evaluation 1)

```
RepoMind/
├── backend/
│   ├── app/
│   │   ├── config.py              # Configuration & environment variables (.env)
│   │   ├── database.py            # SQLAlchemy 2.0 engine, SessionLocal & get_db
│   │   ├── security.py            # Argon2 password hashing & JWT bearer token auth
│   │   ├── main.py                # FastAPI app & router mounts under /api
│   │   ├── models/                # SQLAlchemy ORM models
│   │   │   ├── user.py            # Users table
│   │   │   ├── repository.py      # Repositories table
│   │   │   ├── issue.py           # Issues table (with JSONB labels)
│   │   │   └── ingestion_job.py   # Ingestion jobs table
│   │   ├── schemas/               # Pydantic validation schemas
│   │   │   ├── user.py
│   │   │   ├── repository.py
│   │   │   ├── issue.py
│   │   │   └── ingestion_job.py
│   │   ├── services/              # Business logic & external services
│   │   │   ├── github_client.py   # GitHub REST API client (httpx)
│   │   │   └── ingestion_service.py # Background task ingestion & upsert
│   │   └── routers/               # API endpoints
│   │       ├── auth.py            # /api/auth/register, /api/auth/login, /api/auth/me
│   │       ├── repositories.py    # /api/repositories CRUD & sync
│   │       ├── issues.py          # /api/repositories/{id}/issues & filters
│   │       └── jobs.py            # /api/jobs/{id} status polling
│   ├── tests/                     # 37 Automated Tests
│   │   ├── conftest.py            # In-memory test DB & authenticated client
│   │   ├── test_auth.py           # 9 auth & registration tests
│   │   ├── test_security.py       # 4 password & JWT tests
│   │   ├── test_repositories.py   # 9 repository CRUD & URL tests
│   │   ├── test_issues.py         # 8 pagination & filter tests
│   │   └── test_jobs_and_ingestion.py # 7 ingestion & GitHub client tests
│   ├── create_tables.py           # Table initialization script
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.ts                 # Typed API client with auto bearer headers
│   │   ├── types.ts               # TypeScript interfaces
│   │   ├── components/
│   │   │   ├── Navbar.tsx         # Brand header & auth controls
│   │   │   ├── AuthModal.tsx      # Login & registration dialog
│   │   │   ├── RepositoryList.tsx # Repository cards & management
│   │   │   ├── AddRepositoryModal.tsx # URL input & live ingestion progress polling
│   │   │   ├── IssueExplorer.tsx  # Filter toolbar & paginated issues table
│   │   │   └── IssueDetailModal.tsx # Full issue detail & markdown view
│   │   ├── App.tsx                # Main SPA container
│   │   ├── index.css              # Modern dark UI theme styling
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── scripts/
│   └── verify_workflow.py         # End-to-end integration check script
├── create_tables.py               # Root table creation script
├── run_backend.py                 # FastAPI server runner
├── .env                           # Environment configuration
└── README.md
```

---

## Setup & Running Guide

### 1. Prerequisites
- **Python**: 3.13+ installed
- **Node.js**: v18+ (tested on Node v24 and npm 11)
- **Database**: SQLite is used by default; PostgreSQL 16+ is optional

Copy `.env.example` to `.env`. To use PostgreSQL instead of the default local
SQLite database, set `DATABASE_URL` to your PostgreSQL connection string.
Replace `JWT_SECRET_KEY` with a random value generated by:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Keep `.env` private; it is excluded from Git.

### 2. Database Initialization
Create database tables using the script:
```bash
python create_tables.py
```

### 3. Running Backend Server
Start the FastAPI server:
```bash
python run_backend.py
```
Or with uvicorn:
```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Built Frontend (when built)**: [http://localhost:8000/app/](http://localhost:8000/app/)

### 4. Running Frontend Development Server
In another terminal, run:
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Testing & Verification

### Running the 37 Automated Tests
Mohit's automated test suite can be run with pytest:
```bash
cd backend
python -m pytest -v
```
**Result**:
```
tests/test_auth.py::test_register_user_success PASSED
tests/test_auth.py::test_register_user_duplicate_email PASSED
tests/test_auth.py::test_register_user_invalid_email PASSED
tests/test_auth.py::test_register_user_short_password PASSED
tests/test_auth.py::test_login_success PASSED
tests/test_auth.py::test_login_invalid_password PASSED
tests/test_auth.py::test_login_nonexistent_user PASSED
tests/test_auth.py::test_get_current_user_me_success PASSED
tests/test_auth.py::test_get_current_user_me_unauthorized PASSED
tests/test_issues.py::test_get_issues_empty PASSED
tests/test_issues.py::test_get_issues_pagination PASSED
tests/test_issues.py::test_get_issues_filter_by_status_open PASSED
tests/test_issues.py::test_get_issues_filter_by_status_closed PASSED
tests/test_issues.py::test_get_issues_filter_by_title_search PASSED
tests/test_issues.py::test_get_issues_filter_by_label PASSED
tests/test_issues.py::test_get_repository_labels_distinct_list PASSED
tests/test_issues.py::test_get_single_issue_details_success_and_not_found PASSED
tests/test_jobs_and_ingestion.py::test_get_ingestion_job_status PASSED
tests/test_jobs_and_ingestion.py::test_get_ingestion_job_not_found PASSED
tests/test_jobs_and_ingestion.py::test_github_client_headers_and_url PASSED
tests/test_jobs_and_ingestion.py::test_github_client_handles_rate_limit_error PASSED
tests/test_jobs_and_ingestion.py::test_github_client_handles_not_found_error PASSED
tests/test_jobs_and_ingestion.py::test_github_client_filters_pull_requests PASSED
tests/test_jobs_and_ingestion.py::test_ingestion_service_e2e_workflow PASSED
tests/test_repositories.py::test_parse_and_validate_github_url_formats PASSED
tests/test_repositories.py::test_parse_invalid_github_url PASSED
tests/test_repositories.py::test_add_repository_creates_job_accepted PASSED
tests/test_repositories.py::test_add_repository_duplicate_conflict PASSED
tests/test_repositories.py::test_add_repository_active_job_conflict PASSED
tests/test_repositories.py::test_list_repositories_empty PASSED
tests/test_repositories.py::test_list_repositories_populated PASSED
tests/test_repositories.py::test_get_repository_by_id_success PASSED
tests/test_repositories.py::test_get_repository_by_id_not_found PASSED
tests/test_security.py::test_password_hashing_and_verification PASSED
tests/test_security.py::test_jwt_create_and_decode_valid PASSED
tests/test_security.py::test_jwt_decode_expired_or_invalid PASSED
tests/test_security.py::test_inactive_user_access_rejected PASSED

======================= 37 passed in ~10s =======================
```

### Running the End-to-End Workflow Verification Script
```bash
python scripts/verify_workflow.py
```
This script executes the entire real-world flow against the database:
- Validates health checks
- Registers & authenticates user with JWT
- Adds a GitHub repository and tests duplicate rejection
- Polls background ingestion job
- Retrieves stored repositories
- Verifies issue retrieval, pagination, status filtering, label filtering, and single issue details.
