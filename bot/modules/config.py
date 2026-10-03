from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ModerationAction, SpamCategory

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SETTINGS_PATH = PROJECT_ROOT / "config.json"
DEFAULT_HISTORY_DB_PATH = PROJECT_ROOT / "message_history.db"
DEFAULT_WHITELIST_DB_PATH = PROJECT_ROOT / "whitelist.db"


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


def positive_integer(data: dict[str, Any], name: str, default: int) -> int:
    value = integer(data, name, default)
    if value <= 0:
        msg = f"{name} must be greater than 0"
        raise RuntimeError(msg)

    return value


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


def spam_category(data: dict[str, Any], name: str, default: SpamCategory) -> SpamCategory:
    raw_value = data.get(name, default.value)
    normalized = str(raw_value).strip().lower()
    for category in SpamCategory:
        if normalized in {category.name.lower(), category.value.lower()}:
            return category

    choices = ", ".join(
        category.value for category in SpamCategory if category is not SpamCategory.NONE
    )
    msg = f"{name} must be one of: {choices}"
    raise RuntimeError(msg)


@dataclass(frozen=True)
class Thresholds:
    possible: int
    likely: int
    certain: int

    @classmethod
    def from_dict(cls, d: dict | None) -> Thresholds:
        p = 2
        l = 4  # noqa: E741
        c = 7

        return (
            cls(possible=p, likely=l, certain=c)
            if not d
            else cls(
                possible=integer(d, "possible", default=p),
                likely=integer(d, "likely", default=l),
                certain=integer(d, "certain", default=c),
            )
        )


@dataclass(frozen=True)
class HistoryDB:
    path: Path
    retention_days: int

    @classmethod
    def from_dict(cls, d: dict | None) -> HistoryDB:
        return (
            cls(path=DEFAULT_HISTORY_DB_PATH, retention_days=90)
            if not d
            else cls(
                path=_history_db_path(opt_str(d, "path")),
                retention_days=positive_integer(d, "retention_days", default=90),
            )
        )


@dataclass(frozen=True)
class WhitelistDB:
    path: Path

    @classmethod
    def from_dict(cls, d: dict | None) -> WhitelistDB:
        return (
            cls(path=DEFAULT_WHITELIST_DB_PATH)
            if not d
            else cls(
                path=_history_db_path(opt_str(d, "path")),
            )
        )


@dataclass(frozen=True)
class Honeypot:
    enabled: bool
    dm: bool
    channel_id: int | None
    action: ModerationAction

    @classmethod
    def from_dict(cls, d: dict | None) -> Honeypot:
        return (
            cls(
                enabled=False,
                dm=False,
                channel_id=None,
                action=ModerationAction.KICK,
            )
            if d is None
            else cls(
                enabled=boolean(d, "enabled", default=False),
                dm=boolean(d, "dm", default=False),
                channel_id=_honeypot_channel_id(d),
                action=mod_action(d, "action", ModerationAction.KICK),
            )
        )


@dataclass(frozen=True)
class Notifications:
    enabled: bool
    channel_id: int
    ping: str | None

    @classmethod
    def from_dict(cls, d: dict | None) -> Notifications:
        return (
            cls(enabled=False, channel_id=0, ping=None)
            if d is None
            else cls(
                enabled=boolean(d, "enabled", default=False),
                channel_id=integer(d, "channel_id", default=0),
                ping=opt_str(d, "ping"),
            )
        )


@dataclass(frozen=True)
class MessageDeletion:
    on_detected_spam: bool
    on_action: bool
    on_detected_spam_min_category: SpamCategory
    on_detected_spam_del_limit: int
    on_action_min_category: SpamCategory
    on_action_del_limit: int

    @classmethod
    def from_dict(cls, d: dict | None) -> MessageDeletion:
        return (
            cls(
                on_detected_spam=False,
                on_action=False,
                on_detected_spam_min_category=SpamCategory.LIKELY,
                on_detected_spam_del_limit=50,
                on_action_min_category=SpamCategory.CERTAIN,
                on_action_del_limit=50,
            )
            if d is None
            else cls(
                on_detected_spam=boolean(d, "on_detected_spam", default=False),
                on_action=boolean(d, "on_action", default=False),
                on_detected_spam_min_category=spam_category(
                    d,
                    "on_detected_spam_min_category",
                    SpamCategory.LIKELY,
                ),
                on_detected_spam_del_limit=positive_integer(
                    d,
                    "on_detected_spam_del_limit",
                    default=50,
                ),
                on_action_min_category=spam_category(
                    d,
                    "on_action_min_category",
                    SpamCategory.CERTAIN,
                ),
                on_action_del_limit=positive_integer(d, "on_action_del_limit", default=50),
            )
        )


@dataclass(frozen=True)
class Settings:
    token: str
    owner_id: int
    guild_id: int
    staff_role: int
    invite_link: str | None
    dm_on_action: bool
    action: ModerationAction

    message_deletion: MessageDeletion
    history_db: HistoryDB
    whitelist_db: WhitelistDB
    honeypot: Honeypot
    thresholds: Thresholds
    notifications: Notifications


def load_settings() -> Settings:
    d = load_json(SETTINGS_PATH)

    return Settings(
        token=req_str(d, "token"),
        owner_id=req_int(d, "owner_id"),
        guild_id=req_int(d, "guild_id"),
        staff_role=req_int(d, "staff_role"),
        invite_link=opt_str(d, "invite_link"),
        dm_on_action=boolean(d, "dm_on_action", default=True),
        action=mod_action(d, "action", ModerationAction.KICK),
        history_db=HistoryDB.from_dict(d.get("history_db")),
        whitelist_db=WhitelistDB.from_dict(d.get("whitelist_db")),
        honeypot=Honeypot.from_dict(d.get("honeypot")),
        thresholds=Thresholds.from_dict(d.get("thresholds")),
        notifications=Notifications.from_dict(d.get("notifications")),
        message_deletion=MessageDeletion.from_dict(d.get("message_deletion")),
    )


def reload_settings() -> Settings:
    return load_settings()


def _honeypot_channel_id(data: dict[str, Any]) -> int | None:
    if not boolean(data, "enabled", default=False):
        return opt_int(data, "channel_id")

    return req_int(data, "channel_id")


def _history_db_path(raw_path: str | None) -> Path:
    if raw_path is None:
        return DEFAULT_HISTORY_DB_PATH

    path = Path(raw_path).expanduser()
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
