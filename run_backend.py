import sys
from pathlib import Path
import uvicorn

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_path))

if __name__ == "__main__":
    print("Starting RepoMind FastAPI Server on http://localhost:8000...")
    print("API Docs: http://localhost:8000/docs")
    print("Frontend: http://localhost:8000/app/")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
