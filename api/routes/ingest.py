import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from api.deps import get_current_user, limiter
from api.schemas import IngestResponse
from core.config import settings
from core.index import IndexStore
from core.logging import log_stage

logger = logging.getLogger("ingest")

router = APIRouter()

ALLOWED_SUFFIXES = (".pdf", ".txt")


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(settings.rate_limit_ingest)
async def ingest_document(
    request: Request,
    file: UploadFile,
    user: str = Depends(get_current_user),
) -> IngestResponse:
    filename = file.filename or "upload"
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise HTTPException(status_code=422, detail="Only PDF and TXT files are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    index: IndexStore = request.app.state.index
    started = time.perf_counter()
    try:
        doc_id, chunks_created, pages = await index.ingest(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_stage(
        logger,
        "ingest complete",
        filename=filename,
        doc_id=doc_id,
        chunks=chunks_created,
        pages=pages,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )
    return IngestResponse(doc_id=doc_id, chunks_created=chunks_created, pages=pages)
