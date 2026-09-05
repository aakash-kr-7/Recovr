"""FastAPI app instantiation and router mounting.

Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import evaluation, transactions, webhooks, demo, config
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    logger.info("RECOVR backend started.")
    yield
    logger.info("RECOVR backend shutting down.")


app = FastAPI(
    title="RECOVR",
    description="Payment-failure triage agent — Razorpay AI Buildathon, "
    "Track 3 (Revenue Recovery). See docs/POSITIONING.md in the repo "
    "root for what this is and isn't claiming.",
    version="0.1.0",
    lifespan=lifespan,
)

# Dev-only CORS: allow the Vite dev server. Tighten before any real
# deployment — this is intentionally permissive for the one-week build.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(transactions.router)
app.include_router(evaluation.router)
app.include_router(demo.router)
app.include_router(config.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
