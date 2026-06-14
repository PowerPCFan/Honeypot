import logging
import os
from datetime import datetime

ANSI = "\033["
RESET = f"{ANSI}0m"
RED = f"{ANSI}31m"
GREEN = f"{ANSI}32m"
YELLOW = f"{ANSI}33m"
PURPLE = f"{ANSI}35m"
DEBUG_GRAY = f"{ANSI}90m"


class Formatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: ARG002, N802
        return (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .strftime(
                "%m/%d/%Y %H:%M:%S %Z",
            )
        )

    def colorize(self, levelno: int, level_name: str) -> str:
        match levelno:
            case logging.DEBUG:
                level_name = f"{DEBUG_GRAY}{level_name}{RESET}"
            case logging.INFO:
                level_name = f"{GREEN}{level_name}{RESET}"
            case logging.WARNING:
                level_name = f"{YELLOW}{level_name}{RESET}"
            case logging.ERROR:
                level_name = f"{RED}{level_name}{RESET}"
            case logging.CRITICAL:
                level_name = f"{PURPLE}{level_name}{RESET}"
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

log_level = (
    logging.DEBUG
    if bool(str(os.getenv("DEBUG", "false")).lower() in {"1", "true", "yes", "on"})
    else logging.INFO
)

logger.setLevel(log_level)
