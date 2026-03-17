"""Search endpoints"""
from fastapi import APIRouter, HTTPException
from typing import List
import time
from app.logger import logger
from api.schemas.request import SearchRequest
from api.schemas.response import SearchResponse, SearchResult
from core.search.semantic_search import SemanticSearch

router = APIRouter(prefix="/search", tags=["search"])

# Global search instance
_search_instance = None

def get_search_engine() -> SemanticSearch:
    global _search_instance
    if _search_instance is None:
        _search_instance = SemanticSearch()
    return _search_instance

@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Search for files"""
    try:
        search_engine = get_search_engine()
        start_time = time.time()
        
        results = search_engine.search(
            query=request.query,
            top_k=request.top_k,
            use_time_ranking=request.use_time_ranking
        )
        
        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.2f}s - Query: '{request.query}'")
        
        return SearchResponse(
            query=request.query,
            results=[SearchResult(**r) for r in results],
            count=len(results),
            timestamp=time.time()
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
