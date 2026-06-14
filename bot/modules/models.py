from dataclasses import dataclass, field
from enum import Enum


class ModerationAction(Enum):
    TIMEOUT = "timeout"
    KICK = "kick"
    BAN = "ban"


class SpamCategory(Enum):
    NONE = "none"
    POSSIBLE = "possible spam"
    LIKELY = "likely spam"
    CERTAIN = "100% spam"


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
