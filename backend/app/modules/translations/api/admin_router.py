from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Locale
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.translations.api.schemas import TranslationEntryItem, UpdateTranslationRequest
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.usecases import (
    ListTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)
from app.modules.translations.usecases.reset_translation import ResetTranslationInput
from app.modules.translations.usecases.update_translation import UpdateTranslationInput
from app.modules.users import UserDto

router = APIRouter(prefix="/translations", tags=["translations"])


def _to_item(entry: TranslationEntryDto) -> TranslationEntryItem:
    return TranslationEntryItem(
        locale=entry.locale,
        message_id=entry.message_id,
        attribute_id=entry.attribute_id,
        value=entry.value,
        default_value=entry.default_value,
    )


@router.get("", response_model=list[TranslationEntryItem])
@inject
async def list_translations(
    use_case: FromDishka[ListTranslationsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[TranslationEntryItem]:
    entries = await use_case(actor)
    return [_to_item(entry) for entry in entries]


@router.put("/{locale}/{message_id}", response_model=TranslationEntryItem)
@inject
async def update_translation(
    locale: Locale,
    message_id: str,
    payload: UpdateTranslationRequest,
    use_case: FromDishka[UpdateTranslationUseCase],
    actor: UserDto = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> TranslationEntryItem:
    try:
        entry = await use_case(
            actor,
            UpdateTranslationInput(
                locale=locale, message_id=message_id, attribute_id=attribute_id, value=payload.value
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_item(entry)


@router.post("/{locale}/{message_id}/reset", response_model=TranslationEntryItem)
@inject
async def reset_translation(
    locale: Locale,
    message_id: str,
    use_case: FromDishka[ResetTranslationUseCase],
    actor: UserDto = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> TranslationEntryItem:
    try:
        entry = await use_case(
            actor,
            ResetTranslationInput(locale=locale, message_id=message_id, attribute_id=attribute_id),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_item(entry)
