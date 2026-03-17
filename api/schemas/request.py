"""Request models"""
from pydantic import BaseModel, Field
from typing import Optional, List

class SearchRequest(BaseModel):
    """Search request schema"""
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    use_time_ranking: bool = Field(default=True)

class IndexRequest(BaseModel):
    """Index file request schema"""
    file_path: str = Field(..., min_length=1)

class IndexDirectoryRequest(BaseModel):
    """Index directory request schema"""
    directory_path: str = Field(..., min_length=1)
    recursive: bool = Field(default=True)
