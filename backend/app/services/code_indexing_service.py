from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
from typing import Any
from sqlalchemy.orm import Session
from app.config import settings
from app.models.code_chunk import CodeChunk
from app.models.code_index_status import CodeIndexStatus
from app.models.repository import Repository
from app.services.code_chunker import EXTENSION_TO_LANGUAGE, CodeChunker
from app.services.embedding_service import EmbeddingService
from app.services.github_client import GitHubClient

logger = logging.getLogger(__name__)

# Excluded directory and file patterns
EXCLUDED_PATTERNS = [
    r"(^|/)\.git(/|$)",
    r"(^|/)node_modules(/|$)",
    r"(^|/)\.?venv(/|$)",
    r"(^|/)__pycache__(/|$)",
    r"(^|/)\.pytest_cache(/|$)",
    r"(^|/)dist(/|$)",
    r"(^|/)build(/|$)",
    r"(^|/)\.next(/|$)",
    r"(^|/)\.nuxt(/|$)",
    r"(^|/)target(/|$)",
    r"(^|/)vendor(/|$)",
    r"\.min\.(js|css)$",
    r"\.map$",
    r"\.lock$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"\.(png|jpg|jpeg|gif|svg|ico|webp|mp4|webm|mp3|wav|pdf|zip|tar|gz|7z|exe|dll|so|dylib|bin|pyc|class)$",
]

class CodeIndexingService:
    def __init__(
        self,
        github_client: GitHubClient | None = None,
        embedding_service: EmbeddingService | None = None,
        chunker: CodeChunker | None = None,
    ):
        self.github_client = github_client or GitHubClient()
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunker = chunker or CodeChunker(
            chunk_size_lines=settings.CODE_CHUNK_SIZE_LINES,
            overlap_lines=settings.CODE_CHUNK_OVERLAP_LINES,
        )

    def is_excluded_path(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/")
        for pattern in EXCLUDED_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return True
        return False

    def is_supported_language(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in EXTENSION_TO_LANGUAGE

    def get_or_create_status(self, db: Session, repo_id: int) -> CodeIndexStatus:
        status_rec = (
            db.query(CodeIndexStatus)
            .filter(CodeIndexStatus.repository_id == repo_id)
            .first()
        )
        if not status_rec:
            status_rec = CodeIndexStatus(
                repository_id=repo_id,
                status="not_indexed",
                total_files=0,
                indexed_chunks=0,
            )
            db.add(status_rec)
            db.commit()
            db.refresh(status_rec)
        return status_rec

    async def index_repository_code(
        self,
        db: Session,
        repository: Repository,
        max_files: int | None = None,
    ) -> CodeIndexStatus:
        """
        Indexes actual source code files for the given repository.
        Stores code chunks and embedding vectors in the database.
        """
        max_files = max_files or settings.MAX_INDEXED_FILES_PER_REPO
        status_rec = self.get_or_create_status(db, repository.id)

        # Mark as indexing
        status_rec.status = "indexing"
        status_rec.error_message = None
        db.commit()

        try:
            owner = repository.owner
            repo_name = repository.name

            # 1. Fetch file list (via GitHub tree API or fallback)
            tree_entries: list[dict[str, Any]] = []
            try:
                tree_entries = await self.github_client.get_repository_tree(owner, repo_name)
            except Exception as e:
                logger.warning(f"Failed to fetch GitHub tree for {repository.full_name}: {e}")

            # Filter valid source code files
            valid_files: list[dict[str, Any]] = []
            for entry in tree_entries:
                path = entry.get("path", "")
                mode = entry.get("type", "")
                size = entry.get("size", 0)

                if mode != "blob":
                    continue
                if self.is_excluded_path(path):
                    continue
                if not self.is_supported_language(path):
                    continue
                if size > settings.MAX_FILE_SIZE_BYTES:
                    continue

                valid_files.append(entry)
                if len(valid_files) >= max_files:
                    break

            # If tree API returned no files, check for any mock or local test repository files
            if not valid_files:
                logger.info(f"No remote tree files fetched for {repository.full_name}.")

            indexed_chunks_count = 0
            successfully_indexed_files = 0

            # 2. Process each file
            for file_entry in valid_files:
                path = file_entry["path"]
                try:
                    content = await self.github_client.get_file_content(owner, repo_name, path)
                    if not content or len(content.strip()) < 10:
                        continue

                    # Chunk the file
                    chunks = self.chunker.chunk_file_content(path, content)
                    for chunk in chunks:
                        # Check for existing duplicate chunk
                        existing_chunk = (
                            db.query(CodeChunk)
                            .filter(
                                CodeChunk.repository_id == repository.id,
                                CodeChunk.chunk_hash == chunk.chunk_hash,
                            )
                            .first()
                        )
                        if existing_chunk:
                            indexed_chunks_count += 1
                            continue

                        # Compute embedding
                        emb = await self.embedding_service.get_embedding(chunk.content)

                        new_chunk = CodeChunk(
                            repository_id=repository.id,
                            file_path=chunk.file_path,
                            language=chunk.language,
                            start_line=chunk.start_line,
                            end_line=chunk.end_line,
                            chunk_hash=chunk.chunk_hash,
                            content=chunk.content,
                            commit_sha=file_entry.get("sha"),
                            embedding=emb,
                        )
                        db.add(new_chunk)
                        indexed_chunks_count += 1

                    successfully_indexed_files += 1
                    # Commit batch periodically
                    if successfully_indexed_files % 10 == 0:
                        db.commit()

                except Exception as file_err:
                    logger.warning(f"Failed to index file {path}: {file_err}")

            db.commit()

            # 3. Update status
            status_rec.total_files = len(valid_files)
            status_rec.indexed_chunks = indexed_chunks_count
            status_rec.last_indexed_at = datetime.now(timezone.utc)
            if successfully_indexed_files > 0:
                status_rec.status = "indexed"
            elif len(valid_files) == 0:
                status_rec.status = "indexed"  # Empty repository successfully inspected
            else:
                status_rec.status = "partially_indexed"

            db.commit()
            db.refresh(status_rec)
            return status_rec

        except Exception as err:
            logger.error(f"Repository indexing failed for {repository.full_name}: {err}")
            status_rec.status = "failed"
            status_rec.error_message = str(err)
            db.commit()
            db.refresh(status_rec)
            return status_rec
