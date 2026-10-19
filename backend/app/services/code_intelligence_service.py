from datetime import datetime
import logging
import re
from typing import Any
import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import settings
from app.models.code_chunk import CodeChunk
from app.models.issue import Issue
from app.models.issue_analysis import IssueAnalysis
from app.models.repository import Repository
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class CodeIntelligenceService:
    def __init__(self, embedding_service: EmbeddingService | None = None):
        self.embedding_service = embedding_service or EmbeddingService()

    async def search_code(
        self,
        db: Session,
        query: str,
        repository_id: int | None = None,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """
        Performs semantic & hybrid code retrieval across indexed code chunks.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        # 1. Generate query embedding
        query_emb = await self.embedding_service.get_embedding(clean_q)

        # 2. Query code chunks from database
        chunk_query = db.query(CodeChunk, Repository.full_name).join(
            Repository, CodeChunk.repository_id == Repository.id
        )
        if repository_id:
            chunk_query = chunk_query.filter(CodeChunk.repository_id == repository_id)

        # Limit initial candidate pool for in-memory re-ranking
        candidates = chunk_query.limit(200).all()
        if not candidates:
            return []

        scored_results: list[dict[str, Any]] = []
        for chunk, repo_full_name in candidates:
            score = self.embedding_service.hybrid_relevance_score(
                query=clean_q,
                query_embedding=query_emb,
                content=chunk.content,
                content_embedding=chunk.embedding,
                file_path=chunk.file_path,
            )
            # Filter negligible matches
            if score >= 0.12:
                scored_results.append(
                    {
                        "id": chunk.id,
                        "type": "code_chunk",
                        "repository_id": chunk.repository_id,
                        "repository_name": repo_full_name,
                        "file_path": chunk.file_path,
                        "language": chunk.language or "text",
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "content": chunk.content,
                        "relevance_score": score,
                    }
                )

        # 3. Sort by relevance descending
        scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)

        # 4. Deduplicate overlapping snippets from the same file & line range
        deduped: list[dict[str, Any]] = []
        seen_ranges: set[str] = set()

        for item in scored_results:
            range_key = f"{item['repository_id']}:{item['file_path']}:{item['start_line'] // 20}"
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)
            deduped.append(item)
            if len(deduped) >= limit:
                break

        return deduped

    async def search_investigations(
        self,
        db: Session,
        query: str,
        repository_id: int | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Searches previously saved AI investigations (IssueAnalysis records).
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        words = [w.strip() for w in re.split(r"[\s,;]+", clean_q) if len(w.strip()) >= 2]
        if not words:
            words = [clean_q]

        inv_query = (
            db.query(IssueAnalysis, Issue, Repository.full_name)
            .join(Issue, IssueAnalysis.issue_id == Issue.id)
            .join(Repository, Issue.repository_id == Repository.id)
        )

        if repository_id:
            inv_query = inv_query.filter(Issue.repository_id == repository_id)

        # Match full query phrase or any individual query terms
        conditions = [
            IssueAnalysis.root_cause_hypothesis.ilike(f"%{clean_q}%"),
            IssueAnalysis.patch_explanation.ilike(f"%{clean_q}%"),
            IssueAnalysis.error_type.ilike(f"%{clean_q}%"),
            IssueAnalysis.fix_target_file.ilike(f"%{clean_q}%"),
            Issue.title.ilike(f"%{clean_q}%"),
        ]
        for w in words:
            w_pat = f"%{w}%"
            conditions.extend([
                IssueAnalysis.root_cause_hypothesis.ilike(w_pat),
                IssueAnalysis.patch_explanation.ilike(w_pat),
                IssueAnalysis.error_type.ilike(w_pat),
                IssueAnalysis.fix_target_file.ilike(w_pat),
                Issue.title.ilike(w_pat),
            ])

        candidates = inv_query.filter(or_(*conditions)).all()

        scored_candidates: list[tuple[float, IssueAnalysis, Issue, str]] = []
        for analysis, issue, repo_full_name in candidates:
            haystack = f"{issue.title or ''} {analysis.error_type or ''} {analysis.root_cause_hypothesis or ''} {analysis.fix_target_file or ''} {analysis.patch_explanation or ''}".lower()
            matched_words = sum(1 for w in words if w.lower() in haystack)
            score = matched_words / max(len(words), 1)
            if clean_q.lower() in haystack:
                score += 0.5
            if analysis.confidence:
                score += float(analysis.confidence) * 0.1
            scored_candidates.append((score, analysis, issue, repo_full_name))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_candidates[:limit]

        results: list[dict[str, Any]] = []
        for _, analysis, issue, repo_full_name in top_matches:
            results.append(
                {
                    "id": analysis.id,
                    "type": "investigation",
                    "issue_id": issue.id,
                    "issue_number": issue.issue_number,
                    "issue_title": issue.title,
                    "repository_id": issue.repository_id,
                    "repository_name": repo_full_name,
                    "priority": analysis.priority,
                    "error_type": analysis.error_type or "Analysis",
                    "root_cause_hypothesis": analysis.root_cause_hypothesis or analysis.patch_explanation,
                    "fix_target_file": analysis.fix_target_file,
                    "confidence": analysis.confidence,
                    "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
                }
            )

        return results

    async def explain_code(
        self,
        db: Session,
        query: str,
        repository_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Generates an evidence-grounded AI explanation based strictly on retrieved code chunks.
        """
        clean_q = query.strip()
        if not clean_q:
            return {
                "query": query,
                "answer": "Please provide a query about the repository code.",
                "evidence_sufficient": False,
                "citations": [],
                "supporting_chunks": [],
            }

        # 1. Retrieve top 4 code chunks
        chunks = await self.search_code(db, clean_q, repository_id=repository_id, limit=4)

        if not chunks or (chunks and chunks[0]["relevance_score"] < 0.15):
            return {
                "query": clean_q,
                "answer": f"No relevant source code evidence was found in the indexed repository files for: \"{clean_q}\". Make sure the repository code has been indexed.",
                "evidence_sufficient": False,
                "citations": [],
                "supporting_chunks": [],
            }

        # 2. Build verified citations strictly referring to actual retrieved chunks
        citations = [
            {
                "file_path": c["file_path"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "language": c["language"],
                "repository_name": c["repository_name"],
                "snippet": c["content"][:280] + ("..." if len(c["content"]) > 280 else ""),
            }
            for c in chunks
        ]

        # 3. Generate answer
        # If external OpenAI key is present, prompt the LLM with strict grounding
        if settings.OPENAI_API_KEY:
            try:
                answer = await self._generate_openai_grounded_answer(clean_q, chunks)
                return {
                    "query": clean_q,
                    "answer": answer,
                    "evidence_sufficient": True,
                    "citations": citations,
                    "supporting_chunks": chunks,
                }
            except Exception as e:
                logger.warning(f"OpenAI explanation call failed, falling back to local synthesis: {e}")

        # Local grounded synthesis engine (zero external dependencies)
        answer = self._synthesize_grounded_answer(clean_q, chunks)
        return {
            "query": clean_q,
            "answer": answer,
            "evidence_sufficient": True,
            "citations": citations,
            "supporting_chunks": chunks,
        }

    def _synthesize_grounded_answer(self, query: str, chunks: list[dict[str, Any]]) -> str:
        """
        Synthesizes a grounded explanation directly from retrieved code chunks without hallucinating.
        """
        primary = chunks[0]
        file_path = primary["file_path"]
        lines = f"{primary['start_line']}–{primary['end_line']}"
        repo = primary["repository_name"]

        # Extract function or class signatures
        signatures: list[str] = []
        for line in primary["content"].splitlines():
            line_str = line.strip()
            if line_str.startswith(("def ", "class ", "async def ", "export function ", "export const ", "interface ", "struct ")):
                signatures.append(line_str.split(":", 1)[0].split("{", 1)[0].strip())

        explanation_lines = [
            f"Based on source code retrieved from **`{repo}`**, the functionality for **\"{query}\"** is implemented in [`{file_path}` (L{lines})].",
            "",
        ]

        if signatures:
            explanation_lines.append("**Key components and signatures:**")
            for sig in signatures[:3]:
                explanation_lines.append(f"- `{sig}`")
            explanation_lines.append("")

        # Add references to other corroborating chunks
        if len(chunks) > 1:
            explanation_lines.append("**Additional supporting references:**")
            for c in chunks[1:]:
                explanation_lines.append(f"- [`{c['file_path']}` (L{c['start_line']}–{c['end_line']})] in `{c['repository_name']}`")
            explanation_lines.append("")

        explanation_lines.append(
            "_All statements above are grounded in retrieved source code snippets. Inspect the supporting citations below for exact implementations._"
        )

        return "\n".join(explanation_lines)

    async def _generate_openai_grounded_answer(self, query: str, chunks: list[dict[str, Any]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        context_blocks = []
        for c in chunks:
            context_blocks.append(
                f"File: {c['file_path']} (lines {c['start_line']}-{c['end_line']}) in {c['repository_name']}:\n```\n{c['content'][:1500]}\n```"
            )
        context_str = "\n\n".join(context_blocks)

        prompt = (
            f"You are RepoMind's AI Code Intelligence Engine. Answer the user query strictly using the following retrieved code evidence.\n"
            f"Do not invent file paths, functions, or line numbers. If the evidence is insufficient, clearly say so.\n\n"
            f"Evidence:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Provide a concise, professional markdown answer citing the exact file paths and line ranges."
        )

        payload = {
            "model": settings.OPENAI_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": "You are a code intelligence assistant. Be concise and strictly factual."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
