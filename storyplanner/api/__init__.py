"""Logosforge HTTP API package.

A thin FastAPI layer that exposes the existing Python core as stable DTOs and
safe actions for a shared React UI (Electron desktop + Web/PWA).  No product
logic lives here — routes delegate to ``storyplanner`` core services.
"""

from storyplanner.api.app import create_api
from storyplanner.api.config import ApiConfig

__all__ = ["create_api", "ApiConfig"]
