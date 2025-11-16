"""
General utility functions for transformations, formatting, etc.
"""
from typing import List

def normalize_states(states_raw: str) -> List[str]:
    """
    Split comma-separated state codes into cleaned list.
    """
    return [s.strip().upper() for s in states_raw.split(",") if s.strip()]

def truncate(text: str, length: int = 200) -> str:
    """
    Truncate long text for previews.
    """
    if text and len(text) > length:
        return text[:length] + "..."
    return text

# TODO: Add caching helpers for frequently accessed queries.
