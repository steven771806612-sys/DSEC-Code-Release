"""Hybrid retrieval service — vector + full-text search with RRF fusion."""
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.rag.embedding_service import embed_text


@dataclass
class RetrievedChunk:
    id: UUID
    content: str
    score: float
    source: str  # rubric / case / review / disagreement
    metadata: dict = field(default_factory=dict)


def reciprocal_rank_fusion(
    *result_lists: list[RetrievedChunk], k: int = 60
) -> list[RetrievedChunk]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion."""
    scores: dict[UUID, float] = {}
    chunks: dict[UUID, RetrievedChunk] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)
            scores[chunk.id] = scores.get(chunk.id, 0.0) + rrf_score
            chunks[chunk.id] = chunk

    merged = sorted(chunks.values(), key=lambda c: scores[c.id], reverse=True)
    for chunk in merged:
        chunk.score = scores[chunk.id]
    return merged


class RetrievalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve_for_page(
        self,
        content_text: str,
        industry: Optional[str] = None,
        region: Optional[str] = None,
        rubric_version: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """
        Full RAG retrieval pipeline for a single case page.
        Returns merged, ranked chunks from all knowledge sources.
        """
        query_embedding = await embed_text(content_text)

        # Parallel retrieval from all sources
        rubric_chunks, case_chunks, review_chunks, disagreement_chunks = (
            await _gather(
                self._retrieve_rubric(query_embedding, rubric_version),
                self._retrieve_cases(
                    query_embedding, content_text, industry, rubric_version
                ),
                self._retrieve_reviews(query_embedding, industry),
                self._retrieve_disagreements(query_embedding),
            )
        )

        # RRF fusion
        merged = reciprocal_rank_fusion(
            rubric_chunks, case_chunks, review_chunks, disagreement_chunks
        )

        # Apply metadata boosts
        for chunk in merged:
            if chunk.metadata.get("is_correction"):
                chunk.score *= chunk.metadata.get("weight_boost", 1.5)
            if chunk.metadata.get("label_source") == "dji":
                chunk.score *= 1.2
            if chunk.metadata.get("industry") == industry:
                chunk.score *= 1.2
            if chunk.metadata.get("region") == region:
                chunk.score *= 1.1

        merged.sort(key=lambda c: c.score, reverse=True)
        total_k = (
            settings.RAG_TOP_K_RUBRIC
            + settings.RAG_TOP_K_CASES
            + settings.RAG_TOP_K_REVIEWS
            + settings.RAG_TOP_K_DISAGREEMENTS
        )
        return merged[:total_k]

    async def _retrieve_rubric(
        self,
        query_embedding: list[float],
        rubric_version: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        where_clause = ""
        if rubric_version:
            where_clause = f"AND version = '{rubric_version}'"

        sql = text(f"""
            SELECT id, content, weight,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM rubric_vectors
            WHERE embedding IS NOT NULL
            {where_clause}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.db.execute(
            sql,
            {"embedding": str(query_embedding), "top_k": settings.RAG_TOP_K_RUBRIC * 2},
        )
        rows = result.fetchall()
        return [
            RetrievedChunk(
                id=row.id,
                content=row.content,
                score=float(row.similarity) * float(row.weight),
                source="rubric",
                metadata={"rubric_version": rubric_version},
            )
            for row in rows
        ]

    async def _retrieve_cases(
        self,
        query_embedding: list[float],
        query_text: str,
        industry: Optional[str] = None,
        rubric_version: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        filters = ["status = 'approved'", "embedding IS NOT NULL"]
        if industry:
            filters.append(f"industry = '{industry}'")
        if rubric_version:
            filters.append(f"rubric_version = '{rubric_version}'")
        where = " AND ".join(filters)

        # Vector search
        vec_sql = text(f"""
            SELECT id, content, industry, region, label_source,
                   overall_score, is_correction, weight_boost,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM case_vectors
            WHERE {where}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        vec_result = await self.db.execute(
            vec_sql,
            {"embedding": str(query_embedding), "top_k": settings.RAG_TOP_K_CASES * 2},
        )

        # Full-text search
        ft_sql = text(f"""
            SELECT id, content, industry, region, label_source,
                   overall_score, is_correction, weight_boost,
                   ts_rank(to_tsvector('english', content),
                           plainto_tsquery('english', :query)) AS bm25_score
            FROM case_vectors
            WHERE {where}
              AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
            ORDER BY bm25_score DESC
            LIMIT :top_k
        """)
        ft_result = await self.db.execute(
            ft_sql,
            {"query": query_text, "top_k": settings.RAG_TOP_K_CASES * 2},
        )

        def row_to_chunk(row, score: float) -> RetrievedChunk:
            return RetrievedChunk(
                id=row.id,
                content=row.content,
                score=score,
                source="case",
                metadata={
                    "industry": row.industry,
                    "region": row.region,
                    "label_source": row.label_source,
                    "overall_score": row.overall_score,
                    "is_correction": row.is_correction,
                    "weight_boost": row.weight_boost,
                },
            )

        vec_chunks = [row_to_chunk(r, float(r.similarity)) for r in vec_result.fetchall()]
        ft_chunks = [row_to_chunk(r, float(r.bm25_score)) for r in ft_result.fetchall()]
        merged = reciprocal_rank_fusion(vec_chunks, ft_chunks)
        return merged[: settings.RAG_TOP_K_CASES]

    async def _retrieve_reviews(
        self,
        query_embedding: list[float],
        industry: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        filters = ["embedding IS NOT NULL"]
        if industry:
            filters.append(f"industry = '{industry}'")
        where = " AND ".join(filters)

        sql = text(f"""
            SELECT id, content, review_type, dimension, decision, score,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM review_vectors
            WHERE {where}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.db.execute(
            sql,
            {"embedding": str(query_embedding), "top_k": settings.RAG_TOP_K_REVIEWS},
        )
        return [
            RetrievedChunk(
                id=row.id,
                content=row.content,
                score=float(row.similarity),
                source="review",
                metadata={
                    "review_type": row.review_type,
                    "dimension": row.dimension,
                    "decision": row.decision,
                    "score": row.score,
                },
            )
            for row in result.fetchall()
        ]

    async def _retrieve_disagreements(
        self, query_embedding: list[float]
    ) -> list[RetrievedChunk]:
        sql = text("""
            SELECT id, content, dimension, severity, weight_boost,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM disagreement_vectors
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.db.execute(
            sql,
            {
                "embedding": str(query_embedding),
                "top_k": settings.RAG_TOP_K_DISAGREEMENTS,
            },
        )
        return [
            RetrievedChunk(
                id=row.id,
                content=row.content,
                score=float(row.similarity) * float(row.weight_boost),
                source="disagreement",
                metadata={
                    "dimension": row.dimension,
                    "severity": row.severity,
                    "is_correction": True,
                    "weight_boost": row.weight_boost,
                },
            )
            for row in result.fetchall()
        ]


async def _gather(*coros):
    """Gather coroutines, returning results in order."""
    import asyncio
    return await asyncio.gather(*coros)
