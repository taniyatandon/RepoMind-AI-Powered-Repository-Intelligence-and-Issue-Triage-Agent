from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401
from app.routers import analysis, auth, issues, jobs, pull_requests, repositories, search

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables are created on startup if using auto-init
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning on startup table creation: {e}")
    yield

app = FastAPI(
    title="RepoMind API",
    description="Open-Source Project Intelligence & Issue Triage Agent Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health & Root endpoints
@app.get("/")
def root():
    return {
        "name": "RepoMind API",
        "description": "Open-Source Project Intelligence & Issue Triage Agent",
        "evaluation": "Evaluation 1",
        "status": "online",
        "docs_url": "/docs",
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "RepoMind API",
        "version": "1.0.0",
    }

# API Router mounted under /api
api_router = APIRouter(prefix="/api")
api_router.add_api_route("/health", health_check, methods=["GET"], tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(repositories.router)
api_router.include_router(issues.router)
api_router.include_router(jobs.router)
api_router.include_router(analysis.router)
api_router.include_router(pull_requests.router)
api_router.include_router(search.router)

app.include_router(api_router)

# Frontend static build serving at /app
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

