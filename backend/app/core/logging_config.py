"""
core/logging_config.py
======================
Structured logging configuration for the Sodio Interest Graph backend.

All loggers write:
  - Timestamp (ISO 8601)
  - Log level
  - Module + function name
  - Message with key=value context

Every service function is expected to log:
  - Entry: function name + input parameters
  - Calculation steps: formula, inputs, intermediate values, result
  - LLM calls: prompt sent, response received, latency
  - Exit: return values + elapsed time
"""

import logging
import sys
import time
from functools import wraps
from typing import Any, Callable


def setup_logging(log_level: str = "DEBUG") -> None:
    """
    Configure root logger with a structured format.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    numeric_level = getattr(logging, log_level.upper(), logging.DEBUG)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(numeric_level)

    # File handler for persistent logs
    file_handler = logging.FileHandler("sodio_backend.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on hot-reload
    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        "[Logging] Logging configured | level=%s | handlers=[stdout, sodio_backend.log]",
        log_level,
    )


def log_function_call(logger: logging.Logger) -> Callable:
    """
    Decorator factory that logs function entry, exit, and elapsed time.

    Usage:
        @log_function_call(logger)
        def my_function(arg1, arg2):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = f"{func.__module__}.{func.__qualname__}"
            logger.debug(
                "[ENTER] %s | args=%s | kwargs=%s",
                func_name,
                _safe_repr(args),
                _safe_repr(kwargs),
            )
            start_ts = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_ts) * 1000
                logger.debug(
                    "[EXIT]  %s | elapsed_ms=%.2f | result=%s",
                    func_name,
                    elapsed_ms,
                    _safe_repr(result),
                )
                return result
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_ts) * 1000
                logger.error(
                    "[ERROR] %s | elapsed_ms=%.2f | exception=%s: %s",
                    func_name,
                    elapsed_ms,
                    type(exc).__name__,
                    exc,
                )
                raise

        return wrapper

    return decorator


def _safe_repr(value: Any, max_len: int = 200) -> str:
    """Return a truncated string representation safe for logging."""
    try:
        s = repr(value)
        if len(s) > max_len:
            return s[:max_len] + "…"
        return s
    except Exception:
        return "<unrepresentable>"
