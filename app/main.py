"""FastAPI Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import app.config as config
from app.logger import logger
from api.routes import search, index, health
from core.watcher.file_watcher import FileWatcher
from core.indexing.index_builder import IndexBuilder
from services.startup_indexer import StartupIndexer

app = FastAPI(
    title="DeepSeekFS API",
    description="Semantic file search engine",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(index.router)
app.include_router(health.router)

_file_watcher = None
_index_builder = None


@app.on_event("startup")
async def startup_event():
    global _file_watcher, _index_builder
    logger.info("🚀 DeepSeekFS API starting...")

    # Shared index builder
    _index_builder = IndexBuilder()

    # ── Auto-scan on startup (background thread) ──
    startup_indexer = StartupIndexer(_index_builder)
    startup_indexer.run_in_background()
    logger.info(f"📂 Watch paths detected: {config.WATCH_PATHS}")

    # ── Start file watcher ──
    _file_watcher = FileWatcher(_index_builder)
    _file_watcher.start()

    logger.info("✅ API ready — indexing running in background")


@app.on_event("shutdown")
async def shutdown_event():
    global _file_watcher
    if _file_watcher:
        _file_watcher.stop()
    logger.info("✅ Shutdown complete")


@app.get("/")
async def root():
    return {
        "message": "DeepSeekFS API",
        "version": "0.2.0",
        "docs": "/docs",
        "watch_paths": config.WATCH_PATHS
    }
