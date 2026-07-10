"""FastAPI application entrypoint. Models and stores are loaded once in lifespan."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from api.routes import health
from core.config import settings
from core.logging import setup_logging

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("starting api service")
    # Later milestones attach shared state here (index, session store, models).
    app.state.index = None
    yield
    logger.info("api service shutting down")


app = FastAPI(
    title="Opkey Procurement RAG Chatbot",
    description="Session-aware RAG chatbot over Oracle Fusion Procurement and "
    "University of Richmond procurement policy documents.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["health"])
