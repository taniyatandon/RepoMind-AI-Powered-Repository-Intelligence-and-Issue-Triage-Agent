from typing import Any
import re
import logging
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

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
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(url, headers=self.headers)
            if response.is_error:
                self._handle_response_error(response, f"{owner}/{repo}")
            return response.json()

    async def get_issues(
        self,
        owner: str,
        repo: str,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieves all issue pages unless max_pages explicitly limits the scope.
        Pull requests returned by GitHub's Issues API are excluded.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {
            "state": "all",
            "per_page": per_page,
            "page": 1,
            "sort": "created",
            "direction": "desc",
        }
        page_data = await self._get_paginated_items(
            url,
            params,
            f"{owner}/{repo} issues",
            max_pages,
        )
        return [item for item in page_data if "pull_request" not in item]

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieves all pull-request pages unless max_pages explicitly limits scope.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {
            "state": "all",
            "per_page": per_page,
            "page": 1,
            "sort": "created",
            "direction": "desc",
        }
        return await self._get_paginated_items(
            url,
            params,
            f"{owner}/{repo} pull requests",
            max_pages,
            log_page_progress=True,
        )

    async def _get_paginated_items(
        self,
        url: str,
        params: dict[str, Any] | None,
        context: str,
        max_pages: int | None,
        log_page_progress: bool = False,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        visited_urls: set[str] = set()
        page_count = 0
        initial_params = dict(params or {})
        endpoint_path = urlsplit(url).path
        base_parts = urlsplit(self.BASE_URL)
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            while url:
                if url in visited_urls:
                    raise GitHubAPIError(
                        f"GitHub returned a repeated pagination link while fetching {context}."
                    )
                visited_urls.add(url)
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                )
                params = None
                page_count += 1
                if response.is_error:
                    if log_page_progress:
                        logger.warning(
                            "GitHub pull-request page failed: page=%d records=0 "
                            "has_next_page=false status_code=%d",
                            page_count,
                            response.status_code,
                        )
                    self._handle_response_error(
                        response, f"{context} (page {page_count})"
                    )
                try:
                    page_data = response.json()
                except ValueError as error:
                    if log_page_progress:
                        logger.warning(
                            "GitHub pull-request page was invalid: page=%d "
                            "records=unknown has_next_page=unknown",
                            page_count,
                        )
                    raise GitHubAPIError(
                        f"GitHub returned invalid JSON while fetching {context} "
                        f"(page {page_count})."
                    ) from error
                if not isinstance(page_data, list) or any(
                    not isinstance(item, dict) for item in page_data
                ):
                    if log_page_progress:
                        logger.warning(
                            "GitHub pull-request page was invalid: page=%d "
                            "records=unknown has_next_page=unknown",
                            page_count,
                        )
                    raise GitHubAPIError(
                        f"GitHub returned an unexpected response while fetching {context} "
                        f"(page {page_count})."
                    )
                items.extend(page_data)

                link_header = getattr(response, "headers", {}).get("link", "")
                next_link = response.links.get("next", {}).get("url")
                if log_page_progress:
                    logger.info(
                        "GitHub pull-request page fetched: page=%d records=%d "
                        "has_next_page=%s",
                        page_count,
                        len(page_data),
                        bool(next_link),
                    )
                if not next_link and re.search(
                    r"\brel\s*=\s*[\"']?next\b",
                    link_header,
                    re.IGNORECASE,
                ):
                    raise GitHubAPIError(
                        f"GitHub returned an invalid pagination link while fetching {context}."
                    )
                if not page_data and not next_link:
                    break
                if max_pages is not None and page_count >= max_pages:
                    break
                if not next_link:
                    if len(page_data) < initial_params.get("per_page", 100):
                        break
                    parts = urlsplit(url)
                    query = dict(parse_qsl(parts.query))
                    next_page = int(query.get("page", initial_params.get("page", 1))) + 1
                    query = {**initial_params, **query, "page": next_page}
                    url = urlunsplit(
                        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
                    )
                    continue
                next_link = urljoin(url, next_link)
                next_parts = urlsplit(next_link)
                if (
                    next_parts.scheme != base_parts.scheme
                    or next_parts.netloc != base_parts.netloc
                    or next_parts.path != endpoint_path
                ):
                    raise GitHubAPIError(
                        f"GitHub returned an unexpected pagination link while fetching {context}."
                    )
                url = next_link
        if log_page_progress:
            logger.info(
                "GitHub pull-request pagination finished: pages_fetched=%d "
                "total_records_fetched=%d has_next_page=%s",
                page_count,
                len(items),
                bool(next_link) if "next_link" in locals() else False,
            )
        return items

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
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
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
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
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
        async with httpx.AsyncClient(timeout=25.0, trust_env=False) as client:
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

        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(raw_url, headers=headers)
            if response.status_code == 200:
                return response.text
            return None
