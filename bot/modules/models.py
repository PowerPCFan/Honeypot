from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModerationAction(Enum):
    TIMEOUT = "timeout"
    KICK = "kick"
    BAN = "ban"


class SpamCategory(Enum):
    NONE = "NONE"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    CERTAIN = "CERTAIN"

    @property
    def rank(self) -> int:
        return {
            SpamCategory.NONE: 0,
            SpamCategory.POSSIBLE: 1,
            SpamCategory.LIKELY: 2,
            SpamCategory.CERTAIN: 3,
        }[self]


@dataclass(frozen=True)
class SpamAssessment:
    category: SpamCategory
    score: int
    factors: list[str] = field(default_factory=list)
    certain_reason: str | None = None

    @property
    def should_notify(self) -> bool:
        return self.category is not SpamCategory.NONE

    @property
    def should_moderate(self) -> bool:
        return self.category is SpamCategory.CERTAIN
