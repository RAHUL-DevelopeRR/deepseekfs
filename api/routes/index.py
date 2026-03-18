"""Indexing endpoints - uses shared singleton index"""
from fastapi import APIRouter, HTTPException
from api.schemas.request import IndexRequest, IndexDirectoryRequest
from api.schemas.response import IndexResponse
from core.indexing.index_builder import get_index

router = APIRouter(prefix="/index", tags=["indexing"])

@router.post("/file", response_model=IndexResponse)
async def index_file(request: IndexRequest):
    try:
        idx = get_index()
        success = idx.add_file(request.file_path)
        idx.save()
        return IndexResponse(
            success=success,
            message="Indexed" if success else "Skipped (duplicate or empty)",
            indexed_count=1 if success else 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/directory", response_model=IndexResponse)
async def index_directory(request: IndexDirectoryRequest):
    try:
        idx = get_index()
        count = idx.index_directory(request.directory_path, request.recursive)
        idx.save()
        return IndexResponse(success=True, message=f"Indexed {count} files", indexed_count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
