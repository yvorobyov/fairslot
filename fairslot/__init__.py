"""fairslot - configurable, verifiable allocation of scarce booking slots."""
from .config import load, presets, DEFAULTS  # noqa: F401
from .engine import run, verify_published, draw_key  # noqa: F401

__version__ = "0.1.0"
