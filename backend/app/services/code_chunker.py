import hashlib
from pathlib import Path
from typing import NamedTuple

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sql": "sql",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".bash": "bash",
}

class ChunkResult(NamedTuple):
    file_path: str
    language: str
    start_line: int
    end_line: int
    content: str
    chunk_hash: str

class CodeChunker:
    def __init__(self, chunk_size_lines: int = 60, overlap_lines: int = 10):
        self.chunk_size = max(20, chunk_size_lines)
        self.overlap = min(overlap_lines, self.chunk_size // 2)

    def detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return EXTENSION_TO_LANGUAGE.get(ext, "text")

    def chunk_file_content(self, file_path: str, content: str) -> list[ChunkResult]:
        """
        Splits source file content into logical line-bounded chunks with start_line and end_line.
        Avoids trivial chunks and computes deterministic sha256 hash.
        """
        lines = content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        language = self.detect_language(file_path)
        chunks: list[ChunkResult] = []

        # If file is short enough, keep it as a single coherent chunk
        if total_lines <= self.chunk_size:
            chunk_content = "\n".join(lines).strip()
            if chunk_content:
                chunk_hash = hashlib.sha256(chunk_content.encode("utf-8")).hexdigest()
                chunks.append(
                    ChunkResult(
                        file_path=file_path,
                        language=language,
                        start_line=1,
                        end_line=total_lines,
                        content=chunk_content,
                        chunk_hash=chunk_hash,
                    )
                )
            return chunks

        # Sliding window with overlap
        step = max(1, self.chunk_size - self.overlap)
        idx = 0

        while idx < total_lines:
            end_idx = min(idx + self.chunk_size, total_lines)
            chunk_lines = lines[idx:end_idx]
            chunk_text = "\n".join(chunk_lines).strip()

            # Discard trivial chunks (e.g., just comments or closing brackets)
            if len(chunk_text) >= 15 and any(c.isalnum() for c in chunk_text):
                chunk_hash = hashlib.sha256(
                    f"{file_path}:{idx + 1}:{end_idx}:{chunk_text}".encode("utf-8")
                ).hexdigest()

                chunks.append(
                    ChunkResult(
                        file_path=file_path,
                        language=language,
                        start_line=idx + 1,
                        end_line=end_idx,
                        content=chunk_text,
                        chunk_hash=chunk_hash,
                    )
                )

            if end_idx >= total_lines:
                break
            idx += step

        return chunks
