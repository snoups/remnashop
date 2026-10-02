from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.emoji_packs.api.schemas import (
    EmojiPackItemResponse,
    EmojiPackListResponse,
    EmojiPackResponse,
    ImportEmojiPackRequest,
)
from app.modules.emoji_packs.dto import EmojiPackDto
from app.modules.emoji_packs.usecases import (
    DeleteEmojiPackUseCase,
    ImportEmojiPackUseCase,
    ListEmojiPacksUseCase,
)

router = APIRouter(prefix="/emoji-packs", tags=["emoji-packs"])


def _to_response(pack: EmojiPackDto) -> EmojiPackResponse:
    return EmojiPackResponse(
        set_name=pack.set_name,
        title=pack.title,
        items=[
            EmojiPackItemResponse.model_validate(item, from_attributes=True) for item in pack.items
        ],
    )


@router.get("", response_model=EmojiPackListResponse)
@inject
async def list_emoji_packs(
    use_case: FromDishka[ListEmojiPacksUseCase],
    actor: Actor = Depends(require_admin),
) -> EmojiPackListResponse:
    items = [_to_response(pack) for pack in await use_case(actor)]
    return EmojiPackListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=EmojiPackResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400),
)
@inject
async def import_emoji_pack(
    payload: ImportEmojiPackRequest,
    use_case: FromDishka[ImportEmojiPackUseCase],
    actor: Actor = Depends(require_admin),
) -> EmojiPackResponse:
    return _to_response(await use_case(actor, payload.link))


@router.delete("/{set_name}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_emoji_pack(
    set_name: str,
    use_case: FromDishka[DeleteEmojiPackUseCase],
    actor: Actor = Depends(require_admin),
) -> Response:
    await use_case(actor, set_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
