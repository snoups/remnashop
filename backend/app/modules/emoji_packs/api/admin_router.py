from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import ValidationError
from app.modules.emoji_packs.api.schemas import (
    EmojiPackItemResponse,
    EmojiPackResponse,
    ImportEmojiPackRequest,
)
from app.modules.emoji_packs.dto import EmojiPackDto
from app.modules.emoji_packs.usecases import (
    DeleteEmojiPackUseCase,
    ImportEmojiPackUseCase,
    ListEmojiPacksUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/emoji-packs", tags=["emoji-packs"])


def _to_response(pack: EmojiPackDto) -> EmojiPackResponse:
    return EmojiPackResponse(
        set_name=pack.set_name,
        title=pack.title,
        items=[
            EmojiPackItemResponse(
                custom_emoji_id=item.custom_emoji_id,
                fallback_emoji=item.fallback_emoji,
                animation_kind=item.animation_kind,
            )
            for item in pack.items
        ],
    )


@router.get("", response_model=list[EmojiPackResponse])
@inject
async def list_emoji_packs(
    use_case: FromDishka[ListEmojiPacksUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[EmojiPackResponse]:
    return [_to_response(pack) for pack in await use_case(actor)]


@router.post("", response_model=EmojiPackResponse, status_code=status.HTTP_201_CREATED)
@inject
async def import_emoji_pack(
    payload: ImportEmojiPackRequest,
    use_case: FromDishka[ImportEmojiPackUseCase],
    actor: UserDto = Depends(require_admin),
) -> EmojiPackResponse:
    try:
        return _to_response(await use_case(actor, payload.link))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/{set_name}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_emoji_pack(
    set_name: str,
    use_case: FromDishka[DeleteEmojiPackUseCase],
    actor: UserDto = Depends(require_admin),
) -> Response:
    await use_case(actor, set_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
