from typing import Any


class RecordingDispatch:
    """Stands in for a taskiq task's .kiq(): records the message instead of
    sending it, satisfying any of the *Dispatch ports."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def kiq(self, **kwargs: Any) -> None:
        self.messages.append(kwargs)
