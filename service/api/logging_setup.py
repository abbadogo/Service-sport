"""Logging for the API: readable text by default, one JSON object per line on request."""

from __future__ import annotations

import json
import logging
import time

# Extra fields a log call may attach (logger.info("...", extra={"rid": ..., "status": ...})).
FIELDS = ("rid", "method", "route", "status", "ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for name in FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                out[name] = value
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, separators=(",", ":"))


def configure_logging(fmt: str = "text", level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
