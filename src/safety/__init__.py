"""Safety layer: secret scrubbing, deterministic FAQ fast-path, output validation."""
from src.safety.router import RouteHit, route
from src.safety.scrub import ScrubResult, scrub
from src.safety.validate import ValidationResult, validate_answer

__all__ = [
    "scrub", "ScrubResult",
    "route", "RouteHit",
    "validate_answer", "ValidationResult",
]
