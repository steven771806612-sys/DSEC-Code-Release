"""RAG evaluation pipeline — calls LLM with retrieved context."""
import json
import time
from typing import Optional
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.rag.embedding_service import get_openai_client
from app.services.rag.retrieval_service import RetrievedChunk

# ── Output Schema ─────────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    dimension: str
    score: Optional[float] = Field(None, ge=0, le=100)
    evidence: str = ""
    issues: list[str] = []
    recommendations: list[str] = []


class AIReviewOutput(BaseModel):
    page_id: str
    overall_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    dimension_scores: list[DimensionScore] = []
    critical_issues: list[dict] = []
    rewrite_suggestions: list[dict] = []
    reference_cases_used: list[str] = []
    reasoning_summary: str = ""
    evaluation_metadata: dict = {}


# ── Prompt Templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a strict and objective case evaluation expert for DJI security solution integrations.

ROLE CONSTRAINTS:
- You evaluate based ONLY on the provided rubric criteria and retrieved context.
- You do NOT hallucinate scores, facts, or references not present in the input.
- You do NOT approve or reject cases — you provide advisory scores and findings only.
- Your output MUST conform exactly to the JSON schema provided.
- If evidence is insufficient to score a dimension, output score: null and explain why.

SCORING PHILOSOPHY:
- Be conservative. Partial evidence = partial score.
- Technical claims without data support should be penalized.
- Comparison to approved reference cases should inform your calibration.

OUTPUT LANGUAGE: Match the language of the case content (zh-CN or en-US)."""


EVALUATION_PROMPT_TEMPLATE = """# Current Evaluation Target
**Page Type**: {page_type}
**Industry**: {industry} | **Region**: {region}
**Rubric Version**: {rubric_version}

# Rubric Criteria (Retrieved)
{rubric_context}

# Reference Cases (Approved, similar industry)
{reference_cases_context}

# Historical Review Notes (for calibration)
{review_notes_context}

# Disagreement Cases (Critical - pay extra attention)
{disagreement_context}

# Case Content to Evaluate
{case_page_content}

# Required JSON Output Schema
```json
{{
  "page_id": "<page_id>",
  "overall_score": <0-100>,
  "confidence": <0.0-1.0>,
  "dimension_scores": [
    {{
      "dimension": "<name>",
      "score": <0-100 or null>,
      "evidence": "<cited text from case>",
      "issues": ["<issue1>"],
      "recommendations": ["<rec1>"]
    }}
  ],
  "critical_issues": [{{"severity": "high|medium|low", "description": "<desc>"}}],
  "rewrite_suggestions": [{{"section": "<name>", "suggestion": "<text>"}}],
  "reference_cases_used": ["<case_id>"],
  "reasoning_summary": "<brief evaluation rationale>"
}}
```

Evaluate the above case page against each rubric dimension. Respond with ONLY the JSON object."""


def _format_chunks(
    chunks: list[RetrievedChunk], source: str, max_chars: int = 2000
) -> str:
    filtered = [c for c in chunks if c.source == source]
    if not filtered:
        return "(No relevant context retrieved)"
    text = ""
    for i, chunk in enumerate(filtered[:5], 1):
        text += f"\n--- [{i}] (score={chunk.score:.3f}) ---\n{chunk.content[:400]}\n"
        if len(text) > max_chars:
            break
    return text.strip()


# ── Evaluator ─────────────────────────────────────────────────────────────────

class EvaluationService:
    def __init__(self):
        self.client: AsyncOpenAI = get_openai_client()

    async def evaluate_page(
        self,
        page_id: UUID,
        page_type: str,
        content_text: str,
        retrieved_chunks: list[RetrievedChunk],
        industry: str = "",
        region: str = "",
        rubric_version: str = "v1.0",
        prompt_version: str = "v1.0",
    ) -> AIReviewOutput:
        start_time = time.time()

        evaluation_prompt = EVALUATION_PROMPT_TEMPLATE.format(
            page_type=page_type,
            industry=industry,
            region=region,
            rubric_version=rubric_version,
            rubric_context=_format_chunks(retrieved_chunks, "rubric"),
            reference_cases_context=_format_chunks(retrieved_chunks, "case"),
            review_notes_context=_format_chunks(retrieved_chunks, "review"),
            disagreement_context=_format_chunks(retrieved_chunks, "disagreement"),
            case_page_content=content_text[:3000],
        )

        response = await self.client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": evaluation_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        raw_content = response.choices[0].message.content or "{}"

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            # Fallback: return minimal valid output
            data = {
                "page_id": str(page_id),
                "overall_score": 0.0,
                "confidence": 0.0,
                "reasoning_summary": "Failed to parse LLM response",
            }

        data["page_id"] = str(page_id)
        data.setdefault("confidence", self._estimate_confidence(retrieved_chunks))
        data["evaluation_metadata"] = {
            "model": settings.OPENAI_CHAT_MODEL,
            "prompt_version": prompt_version,
            "retrieval_count": len(retrieved_chunks),
            "latency_ms": latency_ms,
        }

        return AIReviewOutput(**data)

    def _estimate_confidence(self, chunks: list[RetrievedChunk]) -> float:
        """Estimate confidence based on retrieval quality."""
        if not chunks:
            return 0.2
        rubric_chunks = [c for c in chunks if c.source == "rubric"]
        if not rubric_chunks:
            return 0.3
        avg_score = sum(c.score for c in rubric_chunks) / len(rubric_chunks)
        # Normalize to 0-1 range (RRF scores are small numbers)
        return min(0.95, avg_score * 50)
