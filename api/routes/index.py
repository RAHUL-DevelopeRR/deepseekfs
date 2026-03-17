"""Indexing endpoints"""
from fastapi import APIRouter, HTTPException
from app.logger import logger
from api.schemas.request import IndexRequest, IndexDirectoryRequest
from api.schemas.response import IndexResponse
from core.indexing.index_builder import IndexBuilder

router = APIRouter(prefix="/index", tags=["indexing"])

# Global index builder instance
_index_builder_instance = None

def get_index_builder() -> IndexBuilder:
    global _index_builder_instance
    if _index_builder_instance is None:
        _index_builder_instance = IndexBuilder()
    return _index_builder_instance

@router.post("/file", response_model=IndexResponse)
async def index_file(request: IndexRequest):
    """Index a single file"""
    try:
        index_builder = get_index_builder()
        success = index_builder.add_file(request.file_path)
        index_builder.save()
        
        return IndexResponse(
            success=success,
            message="File indexed successfully" if success else "File not indexed (empty or unsupported)",
            indexed_count=1 if success else 0
        )
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/directory", response_model=IndexResponse)
async def index_directory(request: IndexDirectoryRequest):
    """Index all files in directory"""
    try:
        index_builder = get_index_builder()
        count = index_builder.index_directory(request.directory_path, request.recursive)
        index_builder.save()
        
        return IndexResponse(
            success=True,
            message=f"Indexed {count} files",
            indexed_count=count
        )
    except Exception as e:
        logger.error(f"Directory indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
