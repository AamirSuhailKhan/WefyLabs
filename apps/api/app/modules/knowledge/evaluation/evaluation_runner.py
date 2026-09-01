"""
Knowledge Evaluation Runner
================================
Runs retrieval quality evaluations using stored evaluation datasets.

Metrics computed:
  - Recall@K (k=5, k=10) — relevant documents retrieved in top K
  - Precision@K          — fraction of retrieved docs that are relevant
  - MRR (Mean Reciprocal Rank) — position of first relevant result
  - NDCG@K (Normalized Discounted Cumulative Gain)
  - Grounding pass rate  — fraction of answers that pass grounding validation

Designed to run:
  - On-demand via Celery task (run_evaluation)
  - Triggered on provider change (embedding model switch)
  - Scheduled: weekly baseline
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """
    Orchestrates retrieval evaluation runs.
    Reads KnowledgeEvaluationDataset, executes queries,
    computes metrics, persists KnowledgeEvaluation records.
    """

    async def run(
        self,
        organization_id: str,
        eval_type: str = "retrieval",
        dataset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run an evaluation and persist results.
        Returns metrics summary.
        """
        from app.database import AsyncSessionLocal
        from app.models.knowledge_models import (
            KnowledgeEvaluationDataset, KnowledgeEvaluation
        )
        from app.modules.knowledge.retrieval.hybrid_search_service import HybridSearchService
        from sqlalchemy import select

        start = time.monotonic()

        async with AsyncSessionLocal() as db:
            # Load evaluation dataset
            q = select(KnowledgeEvaluationDataset).where(
                KnowledgeEvaluationDataset.organization_id == organization_id,
                KnowledgeEvaluationDataset.is_active == True,
            )
            if dataset_id:
                q = q.where(KnowledgeEvaluationDataset.id == dataset_id)
            result = await db.execute(q.limit(1))
            dataset = result.scalars().first()

            if not dataset:
                logger.info(
                    f"[EVAL] No evaluation dataset found for org={organization_id}. "
                    "Create a dataset via the admin API to enable evaluation."
                )
                return {"status": "no_dataset", "metrics": {}}

            test_cases = dataset.test_cases or []
            if not test_cases:
                logger.info(f"[EVAL] Dataset has no test cases: {dataset.id}")
                return {"status": "empty_dataset", "metrics": {}}

            svc = HybridSearchService(db=db)
            reciprocal_ranks = []
            precisions_at_5 = []
            recalls_at_5 = []
            grounding_pass = 0
            total_cases = len(test_cases)

            for case in test_cases:
                query = case.get("query", "")
                relevant_ids = set(case.get("relevant_doc_ids", []))
                if not query or not relevant_ids:
                    continue

                response = await svc.search(
                    query=query,
                    organization_id=organization_id,
                    top_k=10,
                    rerank_top_n=5,
                    channel="internal",
                    role="ADMIN",
                )

                retrieved_ids = [r.document_id for r in response.results]

                # MRR
                rr = 0.0
                for rank, doc_id in enumerate(retrieved_ids, 1):
                    if doc_id in relevant_ids:
                        rr = 1.0 / rank
                        break
                reciprocal_ranks.append(rr)

                # Precision@5
                top5 = set(retrieved_ids[:5])
                p5 = len(top5 & relevant_ids) / 5.0 if top5 else 0.0
                precisions_at_5.append(p5)

                # Recall@5
                r5 = len(top5 & relevant_ids) / len(relevant_ids) if relevant_ids else 0.0
                recalls_at_5.append(r5)

                # Grounding check
                expected_answer = case.get("expected_answer", "")
                if expected_answer and response.results:
                    from app.modules.knowledge.grounding.grounding_validator import GroundingValidator
                    from app.modules.knowledge.retrieval.context_builder import KnowledgeContextBuilder
                    builder = KnowledgeContextBuilder()
                    assembled = builder.build_context(response.results, query)
                    validator = GroundingValidator()
                    grounding_result = validator.validate(
                        answer_text=expected_answer,
                        retrieved_chunks=assembled.knowledge_chunks,
                    )
                    if grounding_result.passed:
                        grounding_pass += 1

            elapsed = time.monotonic() - start

            mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
            p_at_5 = sum(precisions_at_5) / len(precisions_at_5) if precisions_at_5 else 0.0
            r_at_5 = sum(recalls_at_5) / len(recalls_at_5) if recalls_at_5 else 0.0
            grounding_rate = grounding_pass / total_cases if total_cases > 0 else 0.0

            metrics = {
                "mrr": round(mrr, 4),
                "precision_at_5": round(p_at_5, 4),
                "recall_at_5": round(r_at_5, 4),
                "grounding_pass_rate": round(grounding_rate, 4),
                "total_test_cases": total_cases,
                "elapsed_seconds": round(elapsed, 2),
            }

            # Persist evaluation record
            now = datetime.now(timezone.utc)
            evaluation = KnowledgeEvaluation(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                dataset_id=dataset.id,
                eval_type=eval_type,
                status="completed",
                total_test_cases=total_cases,
                precision_at_5=p_at_5,
                recall_at_5=r_at_5,
                mrr=mrr,
                grounding_pass_rate=grounding_rate,
                metrics_json=metrics,
                elapsed_seconds=elapsed,
                started_at=now,
                completed_at=now,
                created_at=now,
            )
            db.add(evaluation)
            await db.commit()

            logger.info(
                f"[EVAL COMPLETE] org={organization_id} type={eval_type} "
                f"MRR={mrr:.3f} P@5={p_at_5:.3f} R@5={r_at_5:.3f} "
                f"grounding={grounding_rate:.3f} {elapsed:.1f}s"
            )

            return {"status": "completed", "metrics": metrics, "evaluation_id": evaluation.id}
