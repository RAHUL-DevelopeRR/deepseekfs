"""
DEPRECATED — Web/Legacy Mode FastAPI Application
=================================================
This module is only used when running the web-mode entry point (``run.py``).
The desktop application (``run_desktop.py``) never imports this file.

Kept for reference and backward compatibility with Docker/server deployments.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import app.config as config
from app.logger import logger
from api.routes import search, index, health
from core.watcher.file_watcher import FileWatcher
from core.indexing.index_builder import get_index
from services.startup_indexer import StartupIndexer

app = FastAPI(title="DeepSeekFS API", version="0.3.0")

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


@app.on_event("startup")
async def startup_event():
    global _file_watcher
    logger.info("🚀 DeepSeekFS starting...")

    # Boot the singleton index (shared by all modules)
    idx = get_index()
    logger.info(f"Index loaded: {idx.get_index_stats()}")

    # Auto-scan real user folders in background
    startup_indexer = StartupIndexer()
    startup_indexer.run_in_background()

    # File watcher uses the same singleton
    _file_watcher = FileWatcher(idx)
    _file_watcher.start()

    logger.info(f"✅ API ready | Watch paths: {config.WATCH_PATHS}")


@app.on_event("shutdown")
async def shutdown_event():
    global _file_watcher
    if _file_watcher:
        _file_watcher.stop()
    logger.info("Shutdown complete")


@app.get("/")
async def root():
    return {
        "message": "DeepSeekFS API v0.3",
        "watch_paths": config.WATCH_PATHS,
        "docs": "/docs"
    }
