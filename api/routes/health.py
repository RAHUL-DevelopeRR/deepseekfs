"""Health check endpoint"""
from fastapi import APIRouter
import os
from app.logger import logger
from api.schemas.response import HealthResponse
from core.indexing.index_builder import IndexBuilder
import app.config as config

router = APIRouter(tags=["health"])

_index_builder_instance = None

def get_index_builder() -> IndexBuilder:
    global _index_builder_instance
    if _index_builder_instance is None:
        _index_builder_instance = IndexBuilder()
    return _index_builder_instance

@router.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        index_builder = get_index_builder()
        stats = index_builder.get_index_stats()
        return HealthResponse(status="healthy", index_stats=stats)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(status="unhealthy", index_stats={})

@router.get("/open")
async def open_file(path: str):
    """Open file in explorer"""
    try:
        import subprocess
        import platform
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
