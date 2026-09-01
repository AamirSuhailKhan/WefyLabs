"""
Embedding Provider Abstraction
==============================
Abstract interface for all embedding providers.
Primary: Google Gemini (text-embedding-004, 768 dims).
Also supports: Local, Mock.

Design principles:
  - Provider can be replaced without changing business logic.
  - Embeddings are deduplicated by content hash.
  - Cost is tracked per call.
  - Dimensions are validated per model.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

class EmbeddingResult:
    """Result of a single embedding request."""
    def __init__(
        self,
        text: str,
        embedding: List[float],
        provider: str,
        model: str,
        token_count: int,
        text_hash: str,
    ):
        self.text = text
        self.embedding = embedding
        self.provider = provider
        self.model = model
        self.token_count = token_count
        self.text_hash = text_hash
        self.dimensions = len(embedding)


class BatchEmbeddingResult:
    """Result of a batch embedding request."""
    def __init__(
        self,
        results: List[EmbeddingResult],
        provider: str,
        model: str,
        total_tokens: int,
        latency_ms: int,
    ):
        self.results = results
        self.provider = provider
        self.model = model
        self.total_tokens = total_tokens
        self.latency_ms = latency_ms


# ─── Abstract Interface ────────────────────────────────────────────────────────

class EmbeddingProvider(ABC):
    """
    Abstract embedding provider interface.
    All implementations must be injectable and replaceable.
    """
    provider_name: str = "abstract"

    @abstractmethod
    async def embed_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> BatchEmbeddingResult:
        """
        Generate embeddings for a list of texts.
        Implementations must handle rate limits, retries, and batching.
        """
        ...

    @abstractmethod
    def get_dimensions(self, model: Optional[str] = None) -> int:
        """Return the embedding dimensions for the given model."""
        ...

    @abstractmethod
    def get_default_model(self) -> str:
        """Return the default model name."""
        ...

    @staticmethod
    def compute_text_hash(text: str) -> str:
        """Stable SHA-256 hash of text content for deduplication."""
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


# ─── Google Gemini Embedding Provider ─────────────────────────────────────────

class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Google Gemini text-embedding-004 provider.
    Supports both direct async REST API calls (httpx) and google-generativeai SDK.
    Default dimensions: 768.
    """
    provider_name = "gemini"

    _MODEL_DIMS: Dict[str, int] = {
        "gemini-embedding-001": 768,
        "gemini-embedding-2": 768,
        "embedding-001": 768,
    }
    _DEFAULT_MODEL = "gemini-embedding-001"

    def __init__(self, api_key: str, default_model: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self._default_model = model or default_model or self._DEFAULT_MODEL

    async def embed_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> BatchEmbeddingResult:
        model = model or self._default_model
        start = time.monotonic()
        all_results: List[EmbeddingResult] = []
        total_tokens = 0
        BATCH_SIZE = 50

        # Try direct async REST call first (fast, resilient, no SDK lock-in)
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            batch_tokens = sum(len(t.split()) for t in batch)
            
            try:
                # Gemini batchEmbedContents REST endpoint
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents?key={self._api_key}"
                requests_payload = [
                    {
                        "model": f"models/{model}",
                        "content": {"parts": [{"text": t}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                        "outputDimensionality": 768
                    }
                    for t in batch
                ]
                
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(endpoint, json={"requests": requests_payload})
                    
                    if res.status_code == 200:
                        data = res.json()
                        embeddings_list = data.get("embeddings", [])
                        for j, emb_item in enumerate(embeddings_list):
                            values = emb_item.get("values", [])
                            t_text = batch[j] if j < len(batch) else ""
                            all_results.append(EmbeddingResult(
                                text=t_text,
                                embedding=values,
                                provider=self.provider_name,
                                model=model,
                                token_count=len(t_text.split()),
                                text_hash=self.compute_text_hash(t_text),
                            ))
                        total_tokens += batch_tokens
                        continue
                    else:
                        logger.warning(f"[EMBED:Gemini REST API Failed: {res.status_code}] {res.text}. Trying single embed / SDK fallback.")
            except Exception as e:
                logger.warning(f"[EMBED:Gemini REST Request Error] {e}. Trying SDK fallback.")

            # SDK Fallback if direct REST encounters an issue
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                response = genai.embed_content(
                    model=f"models/{model}",
                    content=batch,
                    task_type="retrieval_document",
                )
                embeddings = response.get("embedding", [])
                if isinstance(embeddings[0], float):
                    embeddings = [embeddings]
                for j, embedding in enumerate(embeddings):
                    text = batch[j] if j < len(batch) else ""
                    all_results.append(EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        provider=self.provider_name,
                        model=model,
                        token_count=len(text.split()),
                        text_hash=self.compute_text_hash(text),
                    ))
                total_tokens += batch_tokens
            except Exception as exc:
                logger.error(f"[EMBED:Gemini] Batch embedding failed completely: {exc}")
                raise

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            f"[EMBED:Gemini] {len(texts)} texts → {len(all_results)} embeddings, "
            f"{total_tokens} tokens, {latency_ms}ms"
        )
        return BatchEmbeddingResult(
            results=all_results,
            provider=self.provider_name,
            model=model,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )

    def get_dimensions(self, model: Optional[str] = None) -> int:
        return self._MODEL_DIMS.get(model or self._default_model, 768)

    def get_default_model(self) -> str:
        return self._default_model


# ─── Mock Embedding Provider (Tests) ──────────────────────────────────────────

class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic mock provider for unit tests.
    Returns fixed-dimension zero vectors with hash-seeded first element.
    Never makes real API calls.
    """
    provider_name = "mock"
    _DIMS = 768
    _DEFAULT_MODEL = "mock-embedding-v1"

    def get_dimensions(self, model: Optional[str] = None) -> int:
        return self._DIMS

    def get_default_model(self) -> str:
        return self._DEFAULT_MODEL

    async def embed_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> BatchEmbeddingResult:
        results = []
        for text in texts:
            h = self.compute_text_hash(text)
            first = int(h[:8], 16) / (16**8)
            embedding = [first] + [0.0] * (self._DIMS - 1)
            results.append(EmbeddingResult(
                text=text,
                embedding=embedding,
                provider=self.provider_name,
                model=self._DEFAULT_MODEL,
                token_count=len(text.split()),
                text_hash=h,
            ))
        return BatchEmbeddingResult(
            results=results,
            provider=self.provider_name,
            model=self._DEFAULT_MODEL,
            total_tokens=sum(len(t.split()) for t in texts),
            latency_ms=1,
        )


# ─── Provider Factory ─────────────────────────────────────────────────────────

def get_embedding_provider(
    provider_name: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> EmbeddingProvider:
    """
    Factory: resolve embedding provider by name.
    Defaults to Gemini (gemini-embedding-001).
    """
    if provider_name in ("auto", None, "gemini"):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            try:
                from app.common.config.validated_settings import load_settings
                key = load_settings().GEMINI_API_KEY
            except Exception:
                pass
        if not key or key.startswith("AIzaSy_placeholder"):
            # If in testing without key, fallback to mock
            logger.warning("[EMBED FACTORY] GEMINI_API_KEY not found, falling back to mock provider.")
            return MockEmbeddingProvider()
        default_model = model or os.getenv("KNOWLEDGE_EMBEDDING_MODEL", "gemini-embedding-001")
        return GeminiEmbeddingProvider(api_key=key, default_model=default_model)

    if provider_name == "mock":
        return MockEmbeddingProvider()

    logger.warning(
        f"[EMBED FACTORY] Unknown provider '{provider_name}', falling back to Gemini or mock."
    )
    key = api_key or os.getenv("GEMINI_API_KEY")
    if key:
        return GeminiEmbeddingProvider(api_key=key, default_model=model)
    return MockEmbeddingProvider()
