import io
from typing import Any

from qrcode import QRCode  # type: ignore[attr-defined]


def render_qr_png(data: str) -> bytes:
    qr: Any = QRCode(box_size=16, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()
