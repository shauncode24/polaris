"""How often one address or one user may ask, over a sliding window.

Three limits:
  * every request, by the caller's address;
  * sign-in and sign-up, by the caller's address, far stricter, because a
    password can be guessed;
  * starting AI work, by user. (How many model calls a user gets in a day is a
    separate limit: llm_budget.py.)

Counts are held in memory: each server process counts for itself, and a
restart clears them.

Behind a proxy every request arrives from the proxy's address, so the proxy
has to be listed in TRUSTED_PROXIES for callers to be told apart.
"""
import ipaddress
import math
import time
from collections import deque
from collections.abc import Callable, Hashable, Sequence

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import settings

TOO_MANY_REQUESTS = "Too many requests."
TOO_MANY_SIGN_INS = "Too many sign-in attempts."
TOO_MUCH_WORK = "You've started a lot of AI work in a short time."

# Under /auth/, but nothing there to guess, and used far more often than a
# sign-in: reading the signed-in user, renewing a session (every page load) and
# ending one.
_NOT_A_SIGN_IN = {"/auth/me", "/auth/refresh", "/auth/logout"}

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class SlidingWindow:
    """At most `limit` hits for each key in any `window` seconds. A limit of 0
    or less means no limit.
    """

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[Hashable, deque[float]] = {}
        self._next_sweep = clock() + window

    def __len__(self) -> int:
        """How many keys are being remembered."""
        return len(self._hits)

    def clear(self) -> None:
        self._hits.clear()

    def hit(self, key: Hashable) -> int | None:
        """Counts a hit and returns None. A key with none left isn't counted:
        the seconds until it has one are returned instead.
        """
        if self.limit <= 0:
            return None
        now = self.clock()
        if now >= self._next_sweep:
            self._forget_idle(now)

        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, math.ceil(hits[0] + self.window - now))
        hits.append(now)
        return None

    def _forget_idle(self, now: float) -> None:
        """Drops keys with nothing left in the window, so that one-off callers
        don't pile up for as long as the server runs. Once a window is enough.
        """
        idle = [key for key, hits in self._hits.items() if now - hits[-1] >= self.window]
        for key in idle:
            del self._hits[key]
        self._next_sweep = now + self.window


requests = SlidingWindow(settings.rate_limit_requests, settings.rate_limit_window_seconds)
sign_ins = SlidingWindow(settings.auth_rate_limit_requests, settings.rate_limit_window_seconds)
ai_work = SlidingWindow(settings.ai_rate_limit_requests, settings.rate_limit_window_seconds)


def _wait_message(reason: str, seconds: int) -> str:
    return f"{reason} Try again in {seconds} second{'' if seconds == 1 else 's'}."


class TooMuchWork(HTTPException):
    def __init__(self, seconds: int):
        super().__init__(
            status_code=429, detail=_wait_message(TOO_MUCH_WORK, seconds),
            headers={"Retry-After": str(seconds)},
        )


def require_ai_slot(user_id) -> None:
    """Counts one piece of AI work the user asked for, or raises `TooMuchWork`."""
    wait = ai_work.hit(str(user_id))
    if wait is not None:
        raise TooMuchWork(wait)


# --- who is calling ----------------------------------------------------------

def _parse_address(text: str) -> IPAddress | None:
    """An address as a proxy may write it, with or without a port."""
    text = text.strip()
    if text.startswith("["):  # [IPv6]:port
        text = text[1:].partition("]")[0]
    elif text.count(":") == 1:  # IPv4:port
        text = text.partition(":")[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    return getattr(address, "ipv4_mapped", None) or address


def client_address(peer: str, forwarded_for: Sequence[str], trusted: Sequence[IPNetwork]) -> str:
    """The address a request came from. `peer` is who connected to us and
    `forwarded_for` the X-Forwarded-For headers it sent.

    The header is only believed from a trusted proxy. Each proxy appends the
    address it heard from, so entries are read from the right until one isn't a
    trusted proxy; anything further left was written by the caller.
    """
    address = _parse_address(peer)
    if address is None:
        return peer
    entries = [entry for header in forwarded_for for entry in header.split(",")]
    while entries and any(address in network for network in trusted):
        forwarded = _parse_address(entries.pop())
        if forwarded is None:
            break
        address = forwarded
    return str(address)


def _bucket(address: str) -> str:
    """What an address is counted under. One IPv6 subscriber has a whole /64
    to send from, so its addresses are counted together.
    """
    parsed = _parse_address(address)
    if isinstance(parsed, ipaddress.IPv6Address):
        return str(ipaddress.ip_network((parsed, 64), strict=False))
    return address


def _refusal(reason: str, seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429, content={"detail": _wait_message(reason, seconds)},
        headers={"Retry-After": str(seconds)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """The two limits by address. /health is left out, for uptime checks."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/health":
            return await call_next(request)

        caller = _bucket(client_address(
            request.client.host if request.client else "unknown",
            request.headers.getlist("x-forwarded-for"),
            settings.trusted_proxies,
        ))
        wait = requests.hit(caller)
        if wait is not None:
            return _refusal(TOO_MANY_REQUESTS, wait)
        if path.startswith("/auth/") and path not in _NOT_A_SIGN_IN:
            wait = sign_ins.hit(caller)
            if wait is not None:
                return _refusal(TOO_MANY_SIGN_INS, wait)
        return await call_next(request)
