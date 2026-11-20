"""
In-process rate limiting for the login endpoint.

Counts recent FAILED login attempts per client IP and per (IP, email),
and blocks further attempts for the rest of a rolling window once a
threshold is crossed. A successful login clears that IP+email's counters.

This is in-memory: it protects a single process (our free-tier single
instance) and resets on restart. It's a brute-force speed bump, not a
distributed limiter — a multi-instance deployment would move this to a
shared store (e.g. Redis).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.core.config import get_settings

_lock = threading.Lock()
_failures: dict[str, list[float]] = defaultdict(list)


def _ip_key(ip: str) -> str:
    return f"ip:{ip}"


def _id_key(ip: str, email: str) -> str:
    return f"id:{ip}:{email.strip().lower()}"


def _recent(key: str, window: float, now: float) -> list[float]:
    """Return (and cache) only this key's timestamps inside the window."""
    times = [t for t in _failures.get(key, []) if now - t < window]
    if times:
        _failures[key] = times
    else:
        _failures.pop(key, None)
    return times


def check_login_allowed(ip: str, email: str) -> float | None:
    """None if the attempt may proceed, else seconds the caller should wait."""
    s = get_settings()
    window = float(s.login_attempt_window_seconds)
    now = time.time()
    with _lock:
        for key, limit in (
            (_ip_key(ip), s.login_max_attempts_per_ip),
            (_id_key(ip, email), s.login_max_attempts_per_email),
        ):
            times = _recent(key, window, now)
            if len(times) >= limit:
                return max(1.0, round(window - (now - times[0]), 1))
    return None


def record_login_failure(ip: str, email: str) -> None:
    now = time.time()
    with _lock:
        _failures[_ip_key(ip)].append(now)
        _failures[_id_key(ip, email)].append(now)


def reset_login_attempts(ip: str, email: str) -> None:
    with _lock:
        _failures.pop(_ip_key(ip), None)
        _failures.pop(_id_key(ip, email), None)


def clear_all() -> None:
    """Wipe all counters — used by tests for isolation."""
    with _lock:
        _failures.clear()
