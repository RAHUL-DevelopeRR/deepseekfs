"""Search endpoint - uses shared singleton index"""
from fastapi import APIRouter, HTTPException
import time
from api.schemas.request import SearchRequest
from api.schemas.response import SearchResponse, SearchResult
from core.search.semantic_search import SemanticSearch

router = APIRouter(prefix="/search", tags=["search"])

_search_engine = None

def get_search_engine() -> SemanticSearch:
    global _search_engine
    if _search_engine is None:
        _search_engine = SemanticSearch()
    return _search_engine

@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        engine = get_search_engine()
        results = engine.search(
            query=request.query,
            top_k=request.top_k,
            use_time_ranking=request.use_time_ranking
        )
        return SearchResponse(
            query=request.query,
            results=[SearchResult(**r) for r in results],
            count=len(results),
            timestamp=time.time()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
