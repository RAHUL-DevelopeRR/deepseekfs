"""Health check endpoint"""
from fastapi import APIRouter
from app.logger import logger
from api.schemas.response import HealthResponse
from core.indexing.index_builder import IndexBuilder

router = APIRouter(tags=["health"])

# Global index builder instance
_index_builder_instance = None

def get_index_builder() -> IndexBuilder:
    global _index_builder_instance
    if _index_builder_instance is None:
        _index_builder_instance = IndexBuilder()
    return _index_builder_instance

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        index_builder = get_index_builder()
        stats = index_builder.get_index_stats()
        
        return HealthResponse(
            status="healthy",
            index_stats=stats
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="unhealthy",
            index_stats={}
        )
