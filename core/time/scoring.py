"""Time-based relevance scoring"""
from datetime import datetime, timedelta
import numpy as np
from typing import Dict

def calculate_time_score(
    file_timestamp: float,
    reference_time: float = None,
    decay_days: int = 30
) -> float:
    """
    Calculate time relevance score (0-1).
    Newer files get higher scores, decays over 'decay_days'.
    """
    if reference_time is None:
        reference_time = datetime.now().timestamp()
    
    # Age in days
    age_seconds = reference_time - file_timestamp
    age_days = age_seconds / (24 * 3600)
    
    if age_days < 0:
        return 1.0  # Future file (edge case)
    
    # Exponential decay
    score = np.exp(-age_days / decay_days)
    return float(np.clip(score, 0, 1))

def get_time_multiplier(query: str) -> float:
    """
    Extract time signal from query.
    Boost recent files when keywords present.
    """
    query_lower = query.lower()
    
    recency_keywords = {
        "recent": 1.5,
        "latest": 1.5,
        "today": 2.0,
        "yesterday": 1.8,
        "this week": 1.4,
        "last week": 1.2,
        "this month": 1.1,
        "old": 0.5,
        "archive": 0.3,
    }
    
    max_multiplier = 1.0
    for keyword, multiplier in recency_keywords.items():
        if keyword in query_lower:
            max_multiplier = max(max_multiplier, multiplier)
    
    return max_multiplier
