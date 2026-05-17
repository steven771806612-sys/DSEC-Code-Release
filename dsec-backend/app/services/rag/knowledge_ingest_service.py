"""Knowledge ingestion service — stores approved case data into vector DB."""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CasePage
from app.models.review import Review, ReviewTypeEnum
from app.models.rag import DisagreementRecord
from app.services.rag.embedding_service import embed_text, extract_keywords


class KnowledgeIngestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_approved_case(
        self,
        case_id: UUID,
        pages: list[CasePage],
        final_score: float,
        industry: str,
        region: str,
        rubric_version: str,
    ) -> int:
        """Embed all pages of an approved case into case_vectors. Returns count."""
        count = 0
        for page in pages:
            if not page.content_text:
                continue

            # Full page embedding
            embedding = await embed_text(page.content_text)
            await self.db.execute(
                text("""
                    INSERT INTO case_vectors
                        (id, content, embedding, case_page_id, case_id,
                         page_type, industry, region, overall_score,
                         label_source, status, rubric_version,
                         is_correction, weight_boost, created_at)
                    VALUES
                        (gen_random_uuid(), :content, :embedding::vector,
                         :page_id, :case_id, :page_type, :industry, :region,
                         :score, 'dji', 'approved', :rubric_version,
                         false, 1.0, NOW())
                """),
                {
                    "content": page.content_text,
                    "embedding": str(embedding),
                    "page_id": str(page.id),
                    "case_id": str(case_id),
                    "page_type": page.page_type.value if page.page_type else None,
                    "industry": industry,
                    "region": region,
                    "score": final_score,
                    "rubric_version": rubric_version,
                },
            )

            # Structured summary embedding
            summary = f"[{page.page_type}] {page.title or ''}\n{extract_keywords(page.content_text)}"
            summary_embedding = await embed_text(summary)
            await self.db.execute(
                text("""
                    INSERT INTO case_vectors
                        (id, content, embedding, case_page_id, case_id,
                         page_type, industry, region, overall_score,
                         label_source, status, rubric_version,
                         is_correction, weight_boost, created_at)
                    VALUES
                        (gen_random_uuid(), :content, :embedding::vector,
                         :page_id, :case_id, :page_type, :industry, :region,
                         :score, 'dji', 'approved', :rubric_version,
                         false, 1.0, NOW())
                """),
                {
                    "content": summary,
                    "embedding": str(summary_embedding),
                    "page_id": str(page.id),
                    "case_id": str(case_id),
                    "page_type": page.page_type.value if page.page_type else None,
                    "industry": industry,
                    "region": region,
                    "score": final_score,
                    "rubric_version": rubric_version,
                },
            )
            count += 2
        return count

    async def ingest_review(self, review: Review, industry: str) -> None:
        """Embed a human review into review_vectors."""
        if not review.recommendations and not review.issues:
            return

        content_parts = []
        if review.issues:
            content_parts.append("Issues: " + "; ".join(
                str(i) for i in review.issues[:5]
            ))
        if review.recommendations:
            content_parts.append("Recommendations: " + "; ".join(
                str(r) for r in review.recommendations[:5]
            ))
        content = "\n".join(content_parts)
        if not content:
            return

        embedding = await embed_text(content)
        await self.db.execute(
            text("""
                INSERT INTO review_vectors
                    (id, content, embedding, review_id, review_type,
                     decision, score, industry, created_at)
                VALUES
                    (gen_random_uuid(), :content, :embedding::vector,
                     :review_id, :review_type, :decision, :score,
                     :industry, NOW())
            """),
            {
                "content": content,
                "embedding": str(embedding),
                "review_id": str(review.id),
                "review_type": review.review_type.value,
                "decision": review.decision.value if review.decision else None,
                "score": review.overall_score,
                "industry": industry,
            },
        )

    async def ingest_disagreement(
        self, record: DisagreementRecord
    ) -> None:
        """Embed a disagreement correction into disagreement_vectors."""
        content = record.human_reasoning or ""
        if not content:
            return

        embedding = await embed_text(content)
        await self.db.execute(
            text("""
                INSERT INTO disagreement_vectors
                    (id, content, embedding, disagreement_id,
                     dimension, severity, is_correction, weight_boost, created_at)
                VALUES
                    (gen_random_uuid(), :content, :embedding::vector,
                     :disagreement_id, :dimension, :severity,
                     true, 1.5, NOW())
            """),
            {
                "content": content,
                "embedding": str(embedding),
                "disagreement_id": str(record.id),
                "dimension": record.dimension,
                "severity": record.severity,
            },
        )

    async def ingest_rubric_chunk(
        self,
        content: str,
        rubric_id: UUID,
        dimension: str,
        version: str,
    ) -> None:
        """Embed a rubric text chunk."""
        embedding = await embed_text(content)
        await self.db.execute(
            text("""
                INSERT INTO rubric_vectors
                    (id, content, embedding, rubric_id, dimension, version,
                     weight, created_at)
                VALUES
                    (gen_random_uuid(), :content, :embedding::vector,
                     :rubric_id, :dimension, :version, 1.0, NOW())
            """),
            {
                "content": content,
                "embedding": str(embedding),
                "rubric_id": str(rubric_id),
                "dimension": dimension,
                "version": version,
            },
        )
