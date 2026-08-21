# backend/app/core/logging_config.py
"""Structured logging configuration — Phase 1 §1.1 (replace print-tracing).

Call configure_logging() exactly once at application startup (main.py).
Every module then uses `logging.getLogger(__name__)` — no per-file setup
needed. The root handler writes a consistent format to stdout so Docker's
log driver captures it unchanged.

Log-level ladder:
  DEBUG   — raw LLM payloads, routine checkpoints (dev only, noisy)
  INFO    — coarse lifecycle events (startup, plan persisted)
  WARNING — graceful degradation paths (LLM fell back to deterministic)
  ERROR   — unexpected failures that require operator attention

Default level is INFO; set LOG_LEVEL=DEBUG in .env to surface raw LLM
JSON during local development.
"""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once.  Idempotent — safe to call more
    than once (the handler list check prevents duplicate handlers).
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers on hot-reload (uvicorn --reload
    # re-imports the module, but the root logger object persists across
    # reloads in the same process).
    if root.handlers:
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)

    # Suppress noisy third-party loggers that would otherwise flood stdout
    # at DEBUG level.
    for noisy in ("httpx", "httpcore", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
