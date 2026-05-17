"""Embedding service — wraps OpenAI embeddings API."""
import asyncio
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a float vector."""
    client = get_openai_client()
    text = text.replace("\n", " ").strip()
    if not text:
        return [0.0] * settings.OPENAI_EMBEDDING_DIMENSION

    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embed multiple texts, batching requests."""
    results: list[list[float]] = []
    client = get_openai_client()

    for i in range(0, len(texts), batch_size):
        batch = [t.replace("\n", " ").strip() or " " for t in texts[i:i + batch_size]]
        response = await client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=batch,
        )
        results.extend([item.embedding for item in response.data])
    return results


def extract_keywords(text: str, max_words: int = 50) -> str:
    """Simple keyword extraction — first N words of the text."""
    words = text.split()
    return " ".join(words[:max_words])
