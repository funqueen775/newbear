"""Adapters that normalize external event payloads into ScoreInput."""

from .common import build_score_input_from_payload
from .newbear_adapter import build_score_input_from_world
from .v04_event_adapter import build_score_input_from_v04_event

__all__ = [
    "build_score_input_from_payload",
    "build_score_input_from_world",
    "build_score_input_from_v04_event",
]
