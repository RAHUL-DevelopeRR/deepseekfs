"""FastAPI Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import app.config as config
from app.logger import logger
from api.routes import search, index, health
from core.watcher.file_watcher import FileWatcher
from core.indexing.index_builder import IndexBuilder

# Create FastAPI app
app = FastAPI(
    title="DeepSeekFS API",
    description="Semantic file search engine",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(index.router)
app.include_router(health.router)

# Global file watcher
_file_watcher = None

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global _file_watcher
    logger.info("🚀 DeepSeekFS API starting...")
    
    try:
        # Initialize index builder
        index_builder = IndexBuilder()
        stats = index_builder.get_index_stats()
        logger.info(f"Index stats: {stats}")
        
        # Start file watcher
        _file_watcher = FileWatcher(index_builder)
        _file_watcher.start()
        
        logger.info("✅ API ready")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global _file_watcher
    logger.info("Shutting down...")
    if _file_watcher:
        _file_watcher.stop()
    logger.info("✅ Shutdown complete")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DeepSeekFS API",
        "version": "0.1.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD
    )
