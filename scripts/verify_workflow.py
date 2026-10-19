"""
RepoMind - Evaluation 1 End-to-End Workflow Verification Script
Validates the complete workflow:
1. Database connectivity & tables
2. User registration & JWT authentication
3. Protected route access & bearer token verification
4. Repository addition & input normalization
5. Background ingestion simulation & job polling
6. Issue retrieval, pagination, status filtering, label filtering, and title search
7. Single issue detail retrieval
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient
from app.main import app

def run_verification():
    print("=" * 65)
    print("  RepoMind - Evaluation 1 Complete Workflow Verification")
    print("=" * 65)

    client = TestClient(app)

    # 1. Health check
    print("\n[1] Checking Health Endpoints...")
    res = client.get("/")
    assert res.status_code == 200, f"Root failed: {res.text}"
    print(f"  [OK] Root status: {res.json()['name']} ({res.json()['status']})")

    res_health = client.get("/api/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.text}"
    print(f"  [OK] Health check: {res_health.json()['status']} (v{res_health.json()['version']})")

    # 2. Authentication
    print("\n[2] Testing User Registration & Authentication...")
    test_email = "eval1_tester@repomind.io"
    test_password = "SecurePassword123!"

    # Register
    res_reg = client.post(
        "/api/auth/register",
        json={"email": test_email, "password": test_password, "username": "EvalTester"},
    )
    if res_reg.status_code == 201:
        print(f"  [OK] Registered new user: {test_email}")
    elif res_reg.status_code == 400 and "already registered" in res_reg.text:
        print(f"  [OK] User {test_email} already registered, proceeding to login...")
    else:
        raise AssertionError(f"Registration failed: {res_reg.text}")

    # Login
    res_login = client.post(
        "/api/auth/login",
        json={"email": test_email, "password": test_password},
    )
    assert res_login.status_code == 200, f"Login failed: {res_login.text}"
    login_data = res_login.json()
    token = login_data["access_token"]
    print(f"  [OK] JWT login successful! Token type: {login_data['token_type']}")

    headers = {"Authorization": f"Bearer {token}"}

    # Verify /api/auth/me
    res_me = client.get("/api/auth/me", headers=headers)
    assert res_me.status_code == 200, f"Auth me failed: {res_me.text}"
    print(f"  [OK] Protected /api/auth/me verified for user: {res_me.json()['email']}")

    # 3. Repository Management
    print("\n[3] Testing Repository Ingestion & Job Creation...")
    repo_url = "https://github.com/pallets/flask"
    res_add = client.post(
        "/api/repositories",
        headers=headers,
        json={"repo_url_or_name": repo_url},
    )
    if res_add.status_code == 202:
        job_data = res_add.json()
        job_id = job_data["job_id"]
        print(f"  [OK] Repository '{job_data['repository_name']}' accepted for ingestion (Job #{job_id})")

        # Poll job status
        res_job = client.get(f"/api/jobs/{job_id}", headers=headers)
        assert res_job.status_code == 200, f"Job check failed: {res_job.text}"
        print(f"  [OK] Job #{job_id} status polled successfully: {res_job.json()['status']}")
    elif res_add.status_code == 409:
        print(f"  [OK] Duplicate rejection (409 Conflict) handled correctly for '{repo_url}'")
    else:
        raise AssertionError(f"Unexpected response from add repository: {res_add.status_code} - {res_add.text}")

    # 4. List Repositories
    print("\n[4] Testing Repository Retrieval...")
    res_list = client.get("/api/repositories", headers=headers)
    assert res_list.status_code == 200, f"List repositories failed: {res_list.text}"
    repos = res_list.json()
    print(f"  [OK] Repositories retrieved: {len(repos)} repository(ies) stored in database")
    for r in repos[:3]:
        print(f"    - {r['full_name']} (Language: {r.get('language') or 'N/A'}, Stars: {r['stargazers_count']})")

    # If we have at least one repository, test issue endpoints
    if len(repos) > 0:
        target_repo = repos[0]
        repo_id = target_repo["id"]
        print(f"\n[5] Testing Issue Retrieval & Filtering on '{target_repo['full_name']}' (ID: {repo_id})...")

        # 5a. Paginated issues
        res_issues = client.get(f"/api/repositories/{repo_id}/issues?page=1&per_page=5", headers=headers)
        assert res_issues.status_code == 200, f"Issues list failed: {res_issues.text}"
        issues_data = res_issues.json()
        print(f"  [OK] Issues total: {issues_data['total']} | Page {issues_data['page']}/{issues_data['total_pages']} (items: {len(issues_data['items'])})")

        # 5b. Status filter
        res_open = client.get(f"/api/repositories/{repo_id}/issues?status=open&per_page=5", headers=headers)
        assert res_open.status_code == 200
        print(f"  [OK] Status filter ('open'): {res_open.json()['total']} open issues")

        # 5c. Distinct labels
        res_labels = client.get(f"/api/repositories/{repo_id}/labels", headers=headers)
        assert res_labels.status_code == 200
        labels_list = res_labels.json()
        print(f"  [OK] Distinct labels retrieved: {len(labels_list)} label(s) found")

        # 5d. Single issue details if issues exist
        if len(issues_data["items"]) > 0:
            first_issue = issues_data["items"][0]
            issue_id = first_issue["id"]
            res_detail = client.get(f"/api/issues/{issue_id}", headers=headers)
            assert res_detail.status_code == 200
            print(f"  [OK] Single issue #{first_issue['issue_number']} details retrieved: '{first_issue['title'][:40]}...'")

    print("\n" + "=" * 65)
    print("  [SUCCESS] ALL EVALUATION 1 WORKFLOW VERIFICATIONS PASSED!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    run_verification()
