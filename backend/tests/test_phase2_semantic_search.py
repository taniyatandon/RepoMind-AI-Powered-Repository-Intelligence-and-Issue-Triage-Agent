from datetime import datetime, timezone
import pytest
from app.models.code_chunk import CodeChunk
from app.models.code_index_status import CodeIndexStatus
from app.models.issue import Issue
from app.models.issue_analysis import IssueAnalysis
from app.models.repository import Repository
from app.services.code_chunker import CodeChunker
from app.services.code_indexing_service import CodeIndexingService
from app.services.code_intelligence_service import CodeIntelligenceService
from app.services.embedding_service import EmbeddingService

def test_code_chunker_small_file():
    chunker = CodeChunker(chunk_size_lines=50, overlap_lines=10)
    content = "def hello():\n    print('world')\n"
    chunks = chunker.chunk_file_content("src/hello.py", content)
    assert len(chunks) == 1
    assert chunks[0].language == "python"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert "def hello" in chunks[0].content
    assert chunks[0].chunk_hash != ""

def test_code_chunker_sliding_window():
    chunker = CodeChunker(chunk_size_lines=20, overlap_lines=5)
    lines = [f"line_{i} = {i} * 2" for i in range(1, 55)]
    content = "\n".join(lines)
    chunks = chunker.chunk_file_content("utils/math_helpers.ts", content)
    assert len(chunks) >= 3
    assert chunks[0].language == "typescript"
    assert chunks[0].start_line == 1
    assert chunks[1].start_line > 1

def test_code_indexing_excluded_paths():
    indexer = CodeIndexingService()
    assert indexer.is_excluded_path("node_modules/react/index.js") is True
    assert indexer.is_excluded_path(".venv/lib/python3.14/site.py") is True
    assert indexer.is_excluded_path("__pycache__/main.cpython-314.pyc") is True
    assert indexer.is_excluded_path("dist/bundle.min.js") is True
    assert indexer.is_excluded_path("assets/banner.png") is True
    assert indexer.is_excluded_path("src/components/Navbar.tsx") is False
    assert indexer.is_excluded_path("backend/app/main.py") is False

def test_embedding_service_hybrid_similarity():
    service = EmbeddingService()
    vec1 = service.local_provider.embed_text("def authenticate_user(token: str):")
    vec2 = service.local_provider.embed_text("def verify_jwt_credentials(auth_token: str):")
    vec3 = service.local_provider.embed_text("const calculateTaxRate = (price: number) => price * 0.1;")

    sim_related = service.cosine_similarity(vec1, vec2)
    sim_unrelated = service.cosine_similarity(vec1, vec3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.0

@pytest.fixture
def phase2_test_data(db_session):
    repo = Repository(
        github_repo_id=5555,
        full_name="tiangolo/fastapi",
        name="fastapi",
        owner="tiangolo",
        description="FastAPI framework, high performance, easy to learn, fast to code",
        html_url="https://github.com/tiangolo/fastapi",
        language="Python",
        stargazers_count=75000,
        forks_count=6000,
        open_issues_count=40,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # 1. Code Chunks
    emb_service = EmbeddingService()
    code_content_auth = """def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    payload = decode_jwt_token(token)
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    return user"""
    emb_auth = emb_service.local_provider.embed_text(code_content_auth)

    chunk1 = CodeChunk(
        repository_id=repo.id,
        file_path="app/security.py",
        language="python",
        start_line=50,
        end_line=75,
        chunk_hash="auth_hash_123",
        content=code_content_auth,
        embedding=emb_auth,
    )

    code_content_diff = """def process_pull_request_diffs(pr_id: int, diff_text: str):
    patch_set = PatchSet(diff_text)
    for patched_file in patch_set:
        save_code_diff(patched_file.source, patched_file.target)"""
    emb_diff = emb_service.local_provider.embed_text(code_content_diff)

    chunk2 = CodeChunk(
        repository_id=repo.id,
        file_path="app/services/diff_service.py",
        language="python",
        start_line=12,
        end_line=30,
        chunk_hash="diff_hash_456",
        content=code_content_diff,
        embedding=emb_diff,
    )

    # 2. Issue & Investigation
    issue = Issue(
        repository_id=repo.id,
        github_issue_id=8881,
        issue_number=105,
        title="Token validation raises KeyError when subject claim missing",
        body="Missing sub claim causes unhandled exception in authentication.",
        state="open",
        author="security_dev",
        labels=[{"name": "security", "color": "d73a4a"}],
        html_url="https://github.com/tiangolo/fastapi/issues/105",
    )
    db_session.add(issue)
    db_session.commit()
    db_session.refresh(issue)

    analysis = IssueAnalysis(
        issue_id=issue.id,
        category="bug",
        priority="P0_CRITICAL",
        confidence=0.92,
        model_version="repomind-triage-v1.0",
        error_type="KeyError: 'sub'",
        root_cause_hypothesis="JWT token payload dictionary missing 'sub' claim causes KeyError during get_current_user evaluation.",
        fix_target_file="app/security.py",
        proposed_code_patch="sub = payload.get('sub')\nif not sub: raise HTTPException(401)",
        patch_explanation="Safely retrieves 'sub' claim from JWT payload with fallback validation.",
        analyzed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([chunk1, chunk2, analysis])

    status = CodeIndexStatus(
        repository_id=repo.id,
        status="indexed",
        total_files=2,
        indexed_chunks=2,
        last_indexed_at=datetime.now(timezone.utc),
    )
    db_session.add(status)
    db_session.commit()

    return {"repo": repo, "chunk1": chunk1, "chunk2": chunk2, "issue": issue, "analysis": analysis}

def test_semantic_code_search_api(client, auth_headers, phase2_test_data):
    # Search for authentication logic
    res = client.get("/api/search?q=where+is+authentication+implemented&mode=code", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "code"
    assert len(data["code_chunks"]) >= 1
    top_chunk = data["code_chunks"][0]
    assert top_chunk["file_path"] == "app/security.py"
    assert "get_current_user" in top_chunk["content"]
    assert top_chunk["relevance_score"] > 0.2

def test_semantic_code_search_diff_endpoint(client, auth_headers, phase2_test_data):
    # Dedicated code search endpoint
    res = client.get("/api/search/code?q=pull+request+diffs+processed", headers=auth_headers)
    assert res.status_code == 200
    chunks = res.json()
    assert len(chunks) >= 1
    assert chunks[0]["file_path"] == "app/services/diff_service.py"
    assert "PatchSet" in chunks[0]["content"]

def test_investigations_search_api(client, auth_headers, phase2_test_data):
    # Search past AI investigations
    res = client.get("/api/search?q=missing+subject+claim+keyerror&mode=investigations", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "investigations"
    assert len(data["investigations"]) >= 1
    inv = data["investigations"][0]
    assert inv["issue_number"] == 105
    assert inv["fix_target_file"] == "app/security.py"
    assert "KeyError" in inv["error_type"]

def test_grounded_ai_explanation_endpoint(client, auth_headers, phase2_test_data):
    # Request grounded explanation
    payload = {"query": "How does RepoMind authenticate users?"}
    res = client.post("/api/search/explain", headers=auth_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_sufficient"] is True
    assert len(data["citations"]) >= 1
    citation = data["citations"][0]
    assert citation["file_path"] == "app/security.py"
    assert citation["start_line"] == 50
    assert "get_current_user" in data["answer"] or "app/security.py" in data["answer"]

def test_grounded_ai_explanation_insufficient_evidence(client, auth_headers, phase2_test_data):
    # Request explanation for completely unindexed topic
    payload = {"query": "Quantum cryptography quantum key distribution"}
    res = client.post("/api/search/explain", headers=auth_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_sufficient"] is False
    assert len(data["citations"]) == 0
    assert "No relevant source code evidence was found" in data["answer"]

def test_repository_indexing_status_api(client, auth_headers, phase2_test_data):
    repo_id = phase2_test_data["repo"].id
    res = client.get(f"/api/repositories/{repo_id}/indexing-status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "indexed"
    assert data["total_files"] == 2
    assert data["indexed_chunks"] == 2

def test_phase1_backward_compatibility(client, auth_headers, phase2_test_data):
    # Existing keyword search still works across repositories, issues, PRs
    res = client.get("/api/search?q=fastapi&mode=keyword", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "keyword"
    assert len(data["repositories"]) >= 1
    assert data["repositories"][0]["full_name"] == "tiangolo/fastapi"
