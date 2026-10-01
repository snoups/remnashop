from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Locale
from app.modules.translations.api.schemas import (
    TranslationEntryItem,
    TranslationEntryListResponse,
    TranslationsExportPayload,
    TranslationsImportResult,
    TranslationTextExportItem,
    UpdateTranslationRequest,
)
from app.modules.translations.dto import TranslationEntryDto, TranslationTextExportDto
from app.modules.translations.usecases import (
    ExportTranslationsUseCase,
    ImportTranslationsUseCase,
    ListTranslationsUseCase,
    ResetAllTranslationsUseCase,
    ResetTranslationUseCase,
    TranslationsImportInput,
    UpdateTranslationUseCase,
)
from app.modules.translations.usecases.reset_translation import ResetTranslationInput
from app.modules.translations.usecases.update_translation import UpdateTranslationInput

router = APIRouter(prefix="/translations", tags=["translations"])


def _to_item(entry: TranslationEntryDto) -> TranslationEntryItem:
    return TranslationEntryItem(
        locale=entry.locale,
        message_id=entry.message_id,
        attribute_id=entry.attribute_id,
        value=entry.value,
        default_value=entry.default_value,
    )


@router.get("", response_model=TranslationEntryListResponse)
@inject
async def list_translations(
    use_case: FromDishka[ListTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationEntryListResponse:
    entries = await use_case(actor)
    items = [_to_item(entry) for entry in entries]
    return TranslationEntryListResponse(items=items, total=len(items))


@router.get("/export", response_model=TranslationsExportPayload)
@inject
async def export_translations(
    use_case: FromDishka[ExportTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationsExportPayload:
    export = await use_case(actor)
    return TranslationsExportPayload(
        version=export.version,
        texts=[
            TranslationTextExportItem(
                locale=text.locale,
                message_id=text.message_id,
                attribute_id=text.attribute_id,
                value=text.value,
            )
            for text in export.texts
        ],
    )


@router.post(
    "/actions/import", response_model=TranslationsImportResult, responses=error_responses(400)
)
@inject
async def import_translations(
    payload: TranslationsExportPayload,
    use_case: FromDishka[ImportTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationsImportResult:
    result = await use_case(
        actor,
        TranslationsImportInput(
            version=payload.version,
            texts=[
                TranslationTextExportDto(
                    locale=text.locale,
                    message_id=text.message_id,
                    attribute_id=text.attribute_id,
                    value=text.value,
                )
                for text in payload.texts
            ],
        ),
    )
    return TranslationsImportResult(applied=result.applied, skipped=result.skipped)


@router.post("/actions/reset-all", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_all_translations(
    use_case: FromDishka[ResetAllTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)


@router.put(
    "/{locale}/{message_id}",
    response_model=TranslationEntryItem,
    responses=error_responses(400, 404),
)
@inject
async def update_translation(
    locale: Locale,
    message_id: str,
    payload: UpdateTranslationRequest,
    use_case: FromDishka[UpdateTranslationUseCase],
    actor: Actor = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> TranslationEntryItem:
    entry = await use_case(
        actor,
        UpdateTranslationInput(
            locale=locale, message_id=message_id, attribute_id=attribute_id, value=payload.value
        ),
    )
    return _to_item(entry)


@router.post(
    "/{locale}/{message_id}/actions/reset",
    response_model=TranslationEntryItem,
    responses=error_responses(404),
)
@inject
async def reset_translation(
    locale: Locale,
    message_id: str,
    use_case: FromDishka[ResetTranslationUseCase],
    actor: Actor = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> TranslationEntryItem:
    entry = await use_case(
        actor,
        ResetTranslationInput(locale=locale, message_id=message_id, attribute_id=attribute_id),
    )
    return _to_item(entry)
