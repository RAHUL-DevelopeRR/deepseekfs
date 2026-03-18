"""Health + open-file endpoints"""
from fastapi import APIRouter
import os
from app.logger import logger
from api.schemas.response import HealthResponse
from core.indexing.index_builder import get_index

router = APIRouter(tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        stats = get_index().get_index_stats()
        return HealthResponse(status="healthy", index_stats=stats)
    except Exception as e:
        return HealthResponse(status="unhealthy", index_stats={})

@router.get("/open")
async def open_file(path: str):
    try:
        import subprocess, platform
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
