import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user, limiter
from api.schemas import EvalQuestionResult, EvalResponse
from core.config import settings
from core.llm import QuotaExceededError
from eval.evaluate import run_evaluation

router = APIRouter()

# One run at a time: concurrent suites would interleave over the shared LLM
# budgets and clobber each other's results.md.
_eval_lock = asyncio.Lock()


@router.get("/evaluate", response_model=EvalResponse)
@limiter.limit(settings.rate_limit_evaluate)
async def evaluate(request: Request, user: str = Depends(get_current_user)) -> EvalResponse:
    """Runs the full suite sequentially through the RPM limiter — expect a few
    minutes on the free tier; progress is logged per question."""
    if _eval_lock.locked():
        raise HTTPException(status_code=409, detail="An evaluation run is already in progress")
    try:
        async with _eval_lock:
            summary = await run_evaluation(request.app.state.index, request.app.state.sessions)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EvalResponse(
        hit_rate=summary["hit_rate"],
        answer_relevance=summary["answer_relevance"],
        faithfulness=summary["faithfulness"],
        keyword_coverage=summary["keyword_coverage"],
        llm_calls=summary["llm_calls"],
        per_question=[
            EvalQuestionResult(
                id=q["id"],
                question=q["question"],
                hit=q["hit"],
                answer_relevance=q["answer_relevance"],
                faithfulness=q["faithfulness"],
                keyword_coverage=q["keyword_coverage"],
                notes=q["notes"],
            )
            for q in summary["per_question"]
        ],
        extra={"duration_s": summary["duration_s"]},
    )
