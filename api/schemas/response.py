"""Response models"""
from pydantic import BaseModel
from typing import List, Dict, Optional

class SearchResult(BaseModel):
    """Individual search result"""
    path: str
    name: str
    extension: str
    size: int
    modified_time: float
    semantic_score: float
    time_score: float
    combined_score: float

class SearchResponse(BaseModel):
    """Search response schema"""
    query: str
    results: List[SearchResult]
    count: int
    timestamp: float

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    index_stats: Dict

class IndexResponse(BaseModel):
    """Index operation response"""
    success: bool
    message: str
    indexed_count: int
