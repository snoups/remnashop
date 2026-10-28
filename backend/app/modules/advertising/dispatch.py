from typing import Protocol


class RecordAdLinkAttributionDispatch(Protocol):
    async def kiq(self, *, user_id: int, ad_link_code: str, channel: str) -> object: ...
