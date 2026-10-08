import re
from typing import Final

PREMIUM_EMOJI_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\[\]]{1,16})\]\(emoji:(\d{1,24})\)")
TELEGRAM_TEXT_LIMIT: Final[int] = 4096
TELEGRAM_CAPTION_LIMIT: Final[int] = 1024


def telegram_length(text: str) -> int:
    # Telegram counts UTF-16 code units; premium emoji markup is sent as its glyph
    sent = PREMIUM_EMOJI_RE.sub(r"\1", text)
    return len(sent.encode("utf-16-le")) // 2
