"""Safety layer: secret scrubbing and a deterministic FAQ fast-path."""
from src.safety.router import RouteHit, route
from src.safety.scrub import ScrubResult, scrub

__all__ = ["scrub", "ScrubResult", "route", "RouteHit"]
