"""TCX running workout statistics, offline and dependency-free."""

from .core import VERSION, summarize, parse_tz

__version__ = VERSION
__all__ = ["VERSION", "summarize", "parse_tz"]
