import io
from typing import Any

from qrcode import QRCode  # type: ignore[attr-defined]

from app.core.enums import AdLinkChannel
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.advertising.dto import AdLinkShareUrlsDto


def render_qr_png(data: str) -> bytes:
    qr: Any = QRCode(box_size=16, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def render_share_qr(urls: AdLinkShareUrlsDto, channel: AdLinkChannel) -> bytes:
    url = urls.bot_url if channel is AdLinkChannel.BOT else urls.webcabinet_url
    if url is None:
        raise NotFoundError("Channel is unavailable", code=ErrorCode.AD_LINK_CHANNEL_UNAVAILABLE)
    return render_qr_png(url)
