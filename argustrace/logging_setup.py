"""Logging configuration.

The project had none: when a run failed, the only trace was the `reason` in
the returned Finding, which tells the person looking at the UI something but
leaves the operator with nothing.

Deliberately plain `logging`, not structured/JSON — this is a local
single-user tool, and a log format that needs a parser to read would be worse
here, not better.

One rule matters more than the format: **never log argv**. Container argv
carries the entity being investigated, which is exactly the sensitive part of
an OSINT lookup, and until recently carried secrets too.
"""

import logging

from argustrace.settings import SETTINGS

_configured = False


def configure() -> None:
    """Set up root logging once. Safe to call from both entry points."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, SETTINGS.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
