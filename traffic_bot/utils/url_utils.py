"""
URL utility functions for traffic bot
"""
import pandas as pd
from typing import Union


def looks_like_url_series(s: pd.Series, sample: int = 25) -> bool:
    """
    Check if a pandas Series contains URL-like values by scanning first N non-null values
    
    Args:
        s: pandas Series to check
        sample: Number of non-null values to check (default: 25)
        
    Returns:
        True if any value looks like a URL, False otherwise
    """
    for v in (str(x) for x in s.dropna().head(sample).tolist()):
        if "http" in v.lower() or "www." in v.lower():
            return True
    return False

