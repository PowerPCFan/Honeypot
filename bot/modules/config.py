import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from modules.models import ModerationAction

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SETTINGS_PATH = PROJECT_ROOT / "config.json"
DEFAULT_HISTORY_DB_PATH = PROJECT_ROOT / "message_history.db"


def req_str(data: dict[str, Any], name: str) -> str:
    raw_value = data.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        msg = f"Missing required setting: {name}"
        raise RuntimeError(msg)

    return str(raw_value).strip()


def opt_str(data: dict[str, Any], name: str) -> str | None:
    raw_value = data.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return None

    return str(raw_value)


def req_int(data: dict[str, Any], name: str) -> int:
    raw_value = data.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        msg = f"Missing required setting: {name}"
        raise RuntimeError(msg)

    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        msg_0 = f"{name} must be a Discord snowflake ID"
        raise RuntimeError(msg_0) from exc


def opt_int(data: dict[str, Any], name: str) -> int | None:
    raw_value = data.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"{name} must be a Discord snowflake ID"
        raise RuntimeError(msg) from exc


def boolean(data: dict[str, Any], name: str, *, default: bool) -> bool:
    raw_value = data.get(name, default)
    if isinstance(raw_value, bool):
        return raw_value

    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}

    return bool(raw_value)


def integer(data: dict[str, Any], name: str, default: int) -> int:
    raw_value = data.get(name, default)
    if raw_value is None or str(raw_value).strip() == "":
        return default

    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"{name} must be an integer"
        raise RuntimeError(msg) from exc


def mod_action(
    data: dict[str, Any],
    name: str,
    default: ModerationAction,
) -> ModerationAction:
    raw_value = data.get(name, default.value)
    normalized = str(raw_value).strip().lower()
    try:
        return ModerationAction(normalized)
    except ValueError as exc:
        choices = ", ".join(action.value for action in ModerationAction)
        msg = f"{name} must be one of: {choices}"
        raise RuntimeError(msg) from exc


@dataclass(frozen=True)
class Thresholds:
    possible: int
    likely: int
    certain: int

    @classmethod
    def from_dict(cls, d: dict | None) -> Self:
        p = 2
        l = 5  # noqa: E741
        c = 9

        return cls(possible=p, likely=l, certain=c) if not d else cls(
            possible=integer(d, "possible", default=p),
            likely=integer(d, "likely", default=l),
            certain=integer(d, "certain", default=c),
        )


@dataclass(frozen=True)
class HistoryDB:
    path: Path
    retention: int

    @classmethod
    def from_dict(cls, d: dict | None) -> Self:
        return cls(path=DEFAULT_HISTORY_DB_PATH, retention=90) if not d else cls(
            path=_history_db_path(opt_str(d, "history_db_path")),
            retention=integer(d, "history_retention_days", default=90),
        )


@dataclass(frozen=True)
class Honeypot:
    enabled: bool
    dm: bool
    channel_id: int | None
    action: ModerationAction
    timeout_seconds: int

    @classmethod
    def from_dict(cls, d: dict | None) -> Self:
        return cls(
            enabled=False,
            dm=False,
            channel_id=None,
            action=ModerationAction.KICK,
            timeout_seconds=3600,
        ) if d is None else cls(
            enabled=boolean(d, "enabled", default=False),
            dm=boolean(d, "dm", default=False),
            channel_id=_honeypot_channel_id(d),
            action=mod_action(d, "action", ModerationAction.KICK),
            timeout_seconds=integer(d, "timeout_seconds", default=3600),
        )


@dataclass(frozen=True)
class Notifications:
    enabled: bool
    channel_id: int
    ping: str | None

    @classmethod
    def from_dict(cls, d: dict | None) -> Self:
        return cls(enabled=False, channel_id=0, ping=None) if d is None else cls(
            enabled=boolean(d, "enabled", default=False),
            channel_id=integer(d, "notification_channel_id", default=0),
            ping=opt_str(d, "likely_spam_ping"),
        )


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int
    invite_link: str | None
    dm_on_action: bool
    action: ModerationAction

    history_db: HistoryDB
    honeypot: Honeypot
    thresholds: Thresholds
    notifications: Notifications


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    d = load_json(path)

    return Settings(
        token=         req_str(d, "token"),
        guild_id=      req_int(d, "guild_id"),
        invite_link=   opt_str(d, "invite_link"),
        dm_on_action=  boolean(d, "dm_on_action", default=True),
        action=        mod_action(d, "action", ModerationAction.KICK),
        history_db=    HistoryDB.from_dict(d.get("history_db")),
        honeypot=      Honeypot.from_dict(d.get("honeypot")),
        thresholds=    Thresholds.from_dict(d.get("thresholds")),
        notifications= Notifications.from_dict(d.get("notifications")),
    )


def _honeypot_channel_id(data: dict[str, Any]) -> int | None:
    if not boolean(data, "enabled", default=False):
        return opt_int(data, "channel_id")

    return req_int(data, "channel_id")


def _history_db_path(raw_path: str | None) -> Path:
    if raw_path is None:
        return DEFAULT_HISTORY_DB_PATH

    path = Path(raw_path)
    if path.is_absolute():
        return path

    return SETTINGS_PATH.parent / path


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        msg = f"Missing settings file: {path}"
        raise RuntimeError(msg) from e
    except json.JSONDecodeError as exc:
        msg_0 = f"{path} is not valid JSON: {exc}"
        raise RuntimeError(msg_0) from exc

    if not isinstance(data, dict):
        msg_1 = f"{path} must contain a JSON object"
        raise TypeError(msg_1)

    return data
