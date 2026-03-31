"""Shared SlowAPI limiter instance (see ``app.core.config`` for limits)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
