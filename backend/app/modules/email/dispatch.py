from typing import Protocol


class SendEmailDispatch(Protocol):
    async def kiq(self, *, to: str, subject: str, text: str, html: str) -> object: ...
