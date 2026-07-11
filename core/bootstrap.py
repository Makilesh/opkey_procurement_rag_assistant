"""Cold-start bootstrap for the knowledge-base index.

Startup order (logged clearly):
1. "volume"    — the persistent Chroma volume already holds an initialized
                 index → use it as-is.
2. "prebuilt"  — copy the committed prebuilt_index/ artifacts into the volume,
                 then use them.
3. "full-ingest" — nothing available → run the normal ingestion pipeline over
                 /data (background task; /health stays responsive).

The prebuilt index is ONLY a first-startup optimization. The ingestion
pipeline remains the authoritative mechanism: delete-all → re-ingest via the
API must work identically with no restart.
"""

import logging
import shutil
from pathlib import Path

from core.config import settings
from core.index import IndexStore

logger = logging.getLogger("bootstrap")


def _volume_initialized(chroma_dir: Path) -> bool:
    registry = chroma_dir / "docs.json"
    return registry.exists() and registry.read_text(encoding="utf-8").strip() not in ("", "{}")


def prepare_index_dir() -> str:
    """Ensure the chroma dir is populated before IndexStore opens it.
    Returns which bootstrap path was taken.

    In server mode (CHROMA_HOST set) the api cannot touch the chroma service's
    files — the index-init compose service seeds the chroma volume from
    prebuilt_index/ before chroma starts, so there is nothing to do here."""
    if settings.chroma_host:
        logger.info("bootstrap: chroma server mode — volume seeding handled by index-init")
        return "server"

    chroma_dir = Path(settings.chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    if _volume_initialized(chroma_dir):
        logger.info("bootstrap: using existing index from persistent volume")
        return "volume"

    prebuilt = Path(settings.prebuilt_index_dir)
    prebuilt_chroma = prebuilt / "chroma"
    if prebuilt_chroma.is_dir() and any(prebuilt_chroma.iterdir()):
        logger.info("bootstrap: copying prebuilt index into persistent volume")
        shutil.copytree(prebuilt_chroma, chroma_dir, dirs_exist_ok=True)
        prebuilt_bm25 = prebuilt / "bm25.pkl"
        if prebuilt_bm25.exists():
            bm25_path = Path(settings.bm25_path)
            bm25_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(prebuilt_bm25, bm25_path)
        return "prebuilt"

    logger.warning(
        "bootstrap: no existing or prebuilt index found — full ingestion over %s "
        "will run in the background (this can take several minutes on CPU)",
        settings.data_dir,
    )
    return "full-ingest"


async def full_ingest_data_dir(index: IndexStore) -> None:
    """Fallback path: ingest every document in /data through the normal pipeline."""
    data_dir = Path(settings.data_dir)
    files = sorted(p for p in data_dir.glob("*") if p.suffix.lower() in (".pdf", ".txt"))
    if not files:
        logger.warning("bootstrap: no documents found in %s", data_dir)
        return
    for path in files:
        logger.info("bootstrap: ingesting %s ...", path.name)
        doc_id, chunks, pages = await index.ingest(path.name, path.read_bytes())
        logger.info(
            "bootstrap: ingested %s (doc_id=%s, %d chunks, %d pages)",
            path.name,
            doc_id,
            chunks,
            pages,
        )
    logger.info("bootstrap: full ingestion complete")
