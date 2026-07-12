import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.deps import get_current_user, limiter
from api.schemas import ChatRequest, ChatResponse, Source
from core.chat_pipeline import chat_once, chat_stream
from core.config import settings
from core.llm import QuotaExceededError
from core.sessions import scoped_session_id

logger = logging.getLogger("chat.route")

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.rate_limit_chat)
async def chat(
    request: Request,
    body: ChatRequest,
    user: str = Depends(get_current_user),
):
    index = request.app.state.index
    store = request.app.state.sessions
    cache = getattr(request.app.state, "semcache", None)
    # Sessions are stored under the JWT subject's namespace; the client keeps
    # using (and seeing) the raw session id it chose.
    scoped_id = scoped_session_id(user, body.session_id)

    if body.doc_filter is not None:
        known = {doc["filename"] for doc in index.list_docs()}
        if body.doc_filter not in known:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown document filter: {body.doc_filter!r} — "
                "use a source_filename from GET /documents",
            )

    if body.stream:
        async def event_stream() -> AsyncIterator[str]:
            try:
                async for event in chat_stream(
                    index, store, scoped_id, body.message, body.doc_filter, cache
                ):
                    if "session_id" in event:
                        event["session_id"] = body.session_id
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except QuotaExceededError as exc:
                yield f"data: {json.dumps({'error': str(exc), 'status': 503})}\n\n"
            except Exception:
                logger.exception("stream failed")
                yield f"data: {json.dumps({'error': 'internal error', 'status': 500})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        answer, sources = await chat_once(
            index, store, scoped_id, body.message, body.doc_filter, cache
        )
    except QuotaExceededError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ChatResponse(
        answer=answer,
        sources=[Source(**source) for source in sources],
        session_id=body.session_id,
    )
