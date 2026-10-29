import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Optional

from app.modules.broadcasts.dto import EmailImageDto
from app.modules.broadcasts.storage import email_image_path
from app.modules.email import EmailBrandDto, InlineImageDto, load_email_logo_image
from app.modules.settings import GetPublicAppearanceImageUseCase


async def read_email_images(
    media_dir: Path, broadcast_id: int, rows: list[EmailImageDto]
) -> Optional[dict[int, InlineImageDto]]:
    # None: a file is missing on disk
    images: dict[int, InlineImageDto] = {}
    for i in rows:
        path = email_image_path(media_dir, broadcast_id, i.id, i.extension)
        try:
            data = await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            return None
        images[i.id] = InlineImageDto(cid=f"img-{i.id}", data=data, content_type=i.content_type)
    return images


async def load_email_logo(
    appearance: GetPublicAppearanceImageUseCase, brand: EmailBrandDto
) -> tuple[EmailBrandDto, Optional[InlineImageDto]]:
    if not brand.has_logo:
        return brand, None
    image = await load_email_logo_image(appearance)
    if image is None:
        return replace(brand, has_logo=False), None
    return brand, InlineImageDto(cid="logo", data=image.data, content_type=image.content_type)
