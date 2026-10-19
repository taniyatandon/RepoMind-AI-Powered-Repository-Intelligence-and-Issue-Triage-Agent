import hashlib
import logging
import math
import re
from typing import Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Dimension for the deterministic local/hybrid embedding vector
EMBEDDING_DIM = 128

SEMANTIC_SYNONYMS = {
    "auth": ["authenticate", "authentication", "auth", "authorize", "authorization", "login", "oauth", "oauth2", "credentials", "token", "jwt", "security", "bearer", "password"],
    "db": ["database", "db", "query", "sql", "models", "session", "store", "table", "schema", "orm", "repository", "crud"],
    "diff": ["diff", "diffs", "patch", "patchset", "changes", "additions", "deletions", "commits", "pr"],
    "validate": ["valid", "validate", "validation", "validator", "verify", "verification", "check", "parse"],
    "err": ["error", "exception", "traceback", "fault", "fail", "failure", "bug", "issue", "crash", "keyerror", "valueerror"],
    "url": ["url", "urls", "uri", "link", "endpoint", "route", "router"],
    "repo": ["repo", "repos", "repository", "repositories", "github"],
    "pr": ["pr", "pull", "request", "merge", "diff"],
}

CONCEPT_MAP: dict[str, str] = {}
for concept, words in SEMANTIC_SYNONYMS.items():
    for w in words:
        CONCEPT_MAP[w.lower()] = concept

def split_code_identifiers(text: str) -> list[str]:
    """
    Tokenizes code into individual words, identifiers, sub-tokens, and semantic concepts.
    Splits camelCase and snake_case (e.g., 'getUserProfile' -> 'get', 'user', 'profile').
    """
    tokens: list[str] = []
    words = re.findall(r"[a-zA-Z0-9_]+", text)
    for word in words:
        wl = word.lower()
        tokens.append(wl)
        if wl in CONCEPT_MAP:
            tokens.append(f"__concept_{CONCEPT_MAP[wl]}__")

        # Split by underscore
        parts = word.split("_")
        for p in parts:
            if p:
                pl = p.lower()
                tokens.append(pl)
                if pl in CONCEPT_MAP:
                    tokens.append(f"__concept_{CONCEPT_MAP[pl]}__")

                # Split camelCase
                camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", p)
                for cp in camel_parts:
                    if len(cp) > 1:
                        cpl = cp.lower()
                        tokens.append(cpl)
                        if cpl in CONCEPT_MAP:
                            tokens.append(f"__concept_{CONCEPT_MAP[cpl]}__")

        # 3-gram and 4-gram character subwords for morphologically related terms
        if len(wl) >= 3 and not wl.startswith("__"):
            for n in (3, 4):
                for i in range(len(wl) - n + 1):
                    tokens.append(f"__sub_{wl[i:i+n]}__")

    return tokens

class HybridEmbeddingProvider:
    """
    Built-in, zero-dependency, deterministic embedding provider.
    Uses subword feature hashing with L2-normalized vector space.
    Produces repeatable, normalized vectors suitable for cosine similarity.
    """
    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = split_code_identifiers(text)
        if not tokens:
            return vec

        for token in tokens:
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0

            if token.startswith("__concept_"):
                weight = 2.2
            elif token.startswith("__sub_"):
                weight = 0.8
            elif len(token) >= 3:
                weight = 1.3
            else:
                weight = 0.5

            vec[idx] += sign * weight

        # L2 unit normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]

        return vec

class EmbeddingService:
    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER.lower()
        self.local_provider = HybridEmbeddingProvider(dim=EMBEDDING_DIM)

    async def get_embedding(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * EMBEDDING_DIM

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                return await self._get_openai_embedding(text)
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed, falling back to local: {e}")
                return self.local_provider.embed_text(text)

        elif self.provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                return await self._get_gemini_embedding(text)
            except Exception as e:
                logger.warning(f"Gemini embedding call failed, falling back to local: {e}")
                return self.local_provider.embed_text(text)

        return self.local_provider.embed_text(text)

    async def _get_openai_embedding(self, text: str) -> list[float]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENAI_EMBEDDING_MODEL,
            "input": text[:8000],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["data"][0]["embedding"]

    async def _get_gemini_embedding(self, text: str) -> list[float]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text[:8000]}]},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["embedding"]["values"]

    @staticmethod
    def cosine_similarity(vec1: list[float] | None, vec2: list[float] | None) -> float:
        if not vec1 or not vec2:
            return 0.0
        min_len = min(len(vec1), len(vec2))
        if min_len == 0:
            return 0.0

        dot_product = sum(vec1[i] * vec2[i] for i in range(min_len))
        norm1 = math.sqrt(sum(vec1[i] * vec1[i] for i in range(min_len)))
        norm2 = math.sqrt(sum(vec2[i] * vec2[i] for i in range(min_len)))

        if norm1 <= 0.0 or norm2 <= 0.0:
            return 0.0

        sim = dot_product / (norm1 * norm2)
        return max(0.0, min(1.0, sim))

    @staticmethod
    def hybrid_relevance_score(
        query: str,
        query_embedding: list[float],
        content: str,
        content_embedding: list[float] | None,
        file_path: str = "",
    ) -> float:
        vector_sim = EmbeddingService.cosine_similarity(query_embedding, content_embedding)

        query_terms = set(w.lower() for w in re.findall(r"\w+", query) if len(w) >= 3)
        if not query_terms:
            return vector_sim

        content_terms = set(w.lower() for w in re.findall(r"\w+", f"{content} {file_path}") if len(w) >= 3)
        matching_terms = query_terms.intersection(content_terms)
        keyword_overlap = len(matching_terms) / len(query_terms) if query_terms else 0.0

        path_boost = 0.0
        if any(term in file_path.lower() for term in query_terms):
            path_boost = 0.15

        # Check concept matching
        concept_match_boost = 0.0
        for term in query_terms:
            if term in CONCEPT_MAP and any(CONCEPT_MAP[term] == CONCEPT_MAP.get(ct) for ct in content_terms):
                concept_match_boost = 0.2
                break

        combined = (0.50 * vector_sim) + (0.30 * keyword_overlap) + path_boost + concept_match_boost
        return round(min(1.0, max(0.0, combined)), 4)
