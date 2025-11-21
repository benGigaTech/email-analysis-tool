import json
import logging
import os
import sys
from typing import Optional

DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_configured = False


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter so we avoid external dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log["stack"] = self.formatStack(record.stack_info)
        return json.dumps(log)


def _resolve_log_level() -> int:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def _resolve_formatter() -> logging.Formatter:
    fmt_choice = os.getenv("LOG_FORMAT", "plain").lower()
    if fmt_choice == "json":
        return JsonFormatter(datefmt=DATE_FORMAT)
    return logging.Formatter(DEFAULT_FORMAT, DATE_FORMAT)


def configure_logging(force: bool = False) -> None:
    global _configured
    if _configured and not force:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_resolve_formatter())

    logging.basicConfig(
        level=_resolve_log_level(),
        handlers=[handler],
        force=True,
    )
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
