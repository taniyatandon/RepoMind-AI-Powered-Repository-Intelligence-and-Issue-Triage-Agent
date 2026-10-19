from typing import Any
import httpx
from app.config import settings

class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class GitHubNotFoundError(GitHubAPIError):
    pass

class GitHubRateLimitError(GitHubAPIError):
    pass

class GitHubAuthError(GitHubAPIError):
    pass

class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoMind-Agent/1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _handle_response_error(self, response: httpx.Response, context: str):
        if response.status_code == 404:
            raise GitHubNotFoundError(f"Repository not found on GitHub: {context}", status_code=404)
        elif response.status_code in (403, 429):
            rate_limit_remaining = response.headers.get("x-ratelimit-remaining", "0")
            if rate_limit_remaining == "0" or "rate limit" in response.text.lower():
                raise GitHubRateLimitError(
                    "GitHub API rate limit exceeded. Please configure GITHUB_TOKEN in .env or try again later.",
                    status_code=response.status_code,
                )
            raise GitHubAPIError(f"Access forbidden by GitHub: {response.text}", status_code=response.status_code)
        elif response.status_code == 401:
            raise GitHubAuthError("GitHub authentication failed. Check your GITHUB_TOKEN.", status_code=401)
        elif response.is_error:
            raise GitHubAPIError(
                f"GitHub API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=self.headers)
            if response.is_error:
                self._handle_response_error(response, f"{owner}/{repo}")
            return response.json()

    async def get_issues(
        self,
        owner: str,
        repo: str,
        max_pages: int = 3,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieves up to max_pages (default 3) of 100 issues for the repository,
        excluding pull requests.
        """
        issues: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
                params = {
                    "state": "all",
                    "per_page": per_page,
                    "page": page,
                    "sort": "created",
                    "direction": "desc",
                }
                response = await client.get(url, headers=self.headers, params=params)
                if response.is_error:
                    self._handle_response_error(response, f"{owner}/{repo} (page {page})")

                page_data = response.json()
                if not isinstance(page_data, list) or len(page_data) == 0:
                    break

                for item in page_data:
                    # Exclude pull requests (GitHub issues API includes PRs with a 'pull_request' key)
                    if "pull_request" in item:
                        continue
                    issues.append(item)

                if len(page_data) < per_page:
                    break

        return issues

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        max_pages: int = 2,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retrieves pull requests for the repository (both open, closed, and merged).
        """
        pulls: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
                params = {
                    "state": "all",
                    "per_page": per_page,
                    "page": page,
                    "sort": "created",
                    "direction": "desc",
                }
                response = await client.get(url, headers=self.headers, params=params)
                if response.is_error:
                    self._handle_response_error(response, f"{owner}/{repo} PRs (page {page})")

                page_data = response.json()
                if not isinstance(page_data, list) or len(page_data) == 0:
                    break

                for item in page_data:
                    pulls.append(item)

                if len(page_data) < per_page:
                    break

        return pulls

    async def get_pull_request_commits(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        max_pages: int = 1,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retrieves commits associated with a specific pull request.
        """
        commits: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/commits"
                params = {"per_page": per_page, "page": page}
                response = await client.get(url, headers=self.headers, params=params)
                if response.is_error:
                    self._handle_response_error(
                        response, f"{owner}/{repo} PR #{pull_number} commits (page {page})"
                    )

                page_data = response.json()
                if not isinstance(page_data, list) or len(page_data) == 0:
                    break

                for item in page_data:
                    commits.append(item)

                if len(page_data) < per_page:
                    break

        return commits

    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        max_pages: int = 2,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retrieves changed files and code diff patches for a specific pull request.
        """
        files: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
                params = {"per_page": per_page, "page": page}
                response = await client.get(url, headers=self.headers, params=params)
                if response.is_error:
                    self._handle_response_error(
                        response, f"{owner}/{repo} PR #{pull_number} files (page {page})"
                    )

                page_data = response.json()
                if not isinstance(page_data, list) or len(page_data) == 0:
                    break

                for item in page_data:
                    files.append(item)

                if len(page_data) < per_page:
                    break

        return files

    async def get_repository_tree(
        self, owner: str, repo: str, default_branch: str = "main"
    ) -> list[dict[str, Any]]:
        """
        Retrieves the repository tree recursively using the GitHub Git Trees API.
        """
        async with httpx.AsyncClient(timeout=25.0) as client:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
            response = await client.get(url, headers=self.headers)
            if response.status_code == 404 and default_branch == "main":
                # Fallback to master
                url_master = f"{self.BASE_URL}/repos/{owner}/{repo}/git/trees/master?recursive=1"
                response = await client.get(url_master, headers=self.headers)

            if response.is_error:
                self._handle_response_error(response, f"{owner}/{repo} tree")

            data = response.json()
            return data.get("tree", [])

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str = "HEAD"
    ) -> str | None:
        """
        Fetches the raw text content of a single repository file.
        """
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(raw_url, headers=headers)
            if response.status_code == 200:
                return response.text
            return None
