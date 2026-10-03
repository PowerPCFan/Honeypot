from __future__ import annotations

import logging
from datetime import datetime

from .global_vars import DEBUG

ANSI = "\033["
RESET = f"{ANSI}0m"
RED = f"{ANSI}31m"
GREEN = f"{ANSI}32m"
YELLOW = f"{ANSI}33m"
PURPLE = f"{ANSI}35m"
DEBUG_GRAY = f"{ANSI}90m"


class Formatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: ARG002, N802
        return datetime.fromtimestamp(record.created).astimezone().strftime("%m/%d/%Y %H:%M:%S %Z")

    def colorize(self, levelno: int, level_name: str) -> str:
        color = {
            logging.DEBUG: DEBUG_GRAY,
            logging.INFO: GREEN,
            logging.WARNING: YELLOW,
            logging.ERROR: RED,
            logging.CRITICAL: PURPLE,
        }.get(levelno)

        if color:
            return f"{color}{level_name}{RESET}"

        return level_name

    def format(self, record: logging.LogRecord) -> str:
        level_name = self.colorize(record.levelno, record.levelname.center(8))

        return (
            f"[ {level_name} ]   {record.getMessage()}   "
            f"{DEBUG_GRAY}[{self.formatTime(record)} ({record.filename}:{record.funcName})]{RESET}"
        )


logger = logging.getLogger("honeypot")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(Formatter())
    logger.addHandler(handler)

logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
