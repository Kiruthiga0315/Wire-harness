"""Backward-compatible settings import for application modules."""

from app.core.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
