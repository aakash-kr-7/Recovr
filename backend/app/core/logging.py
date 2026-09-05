"""Structured logging setup.

Deliberately simple: this project's real audit trail is the AuditEntry
table (app/models/audit_entry.py), not application logs. This logger is
for operational visibility only (startup, errors, webhook receipt) — it is
never the source of truth for "what did the agent decide and why."
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
