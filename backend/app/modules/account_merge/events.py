from dataclasses import dataclass, field
from typing import ClassVar

from app.core.actor import Actor
from app.core.events import ActorTargetEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class AccountsMergedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    # the account as it was before anonymize()
    source: Actor
    choices: dict[str, str] = field(default_factory=dict)
