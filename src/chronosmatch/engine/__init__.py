"""Engine package providing limit order books and matching components.

Attempts to import the Cython implementation; if unavailable, falls back to pure Python.
"""

from .matching import MatchingEngine
from .order_book import LimitOrderBook

try:
    from .cython_lob import CythonLimitOrderBook  # type: ignore

    __all__ = ["LimitOrderBook", "MatchingEngine", "CythonLimitOrderBook"]
except Exception:  # pragma: no cover
    CythonLimitOrderBook = None  # type: ignore
    __all__ = ["LimitOrderBook", "MatchingEngine"]
