from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Locale
from app.modules.translations.api.schemas import (
    ActiveLocalesResponse,
    TranslationEntryListResponse,
    TranslationEntryResponse,
    TranslationsExportResponse,
    TranslationsImportRequest,
    TranslationsImportResponse,
    UpdateLocalesRequest,
    UpdateTranslationRequest,
)
from app.modules.translations.dto import (
    ResetTranslationDto,
    TranslationsImportDto,
    TranslationTextExportDto,
    UpdateTranslationDto,
)
from app.modules.translations.usecases import (
    AddLocaleUseCase,
    ExportTranslationsUseCase,
    ImportTranslationsUseCase,
    ListActiveLocalesUseCase,
    ListTranslationsUseCase,
    RemoveLocaleUseCase,
    ResetAllTranslationsUseCase,
    ResetTranslationUseCase,
    SetDefaultLocaleUseCase,
    UpdateTranslationUseCase,
)

router = APIRouter(prefix="/translations", tags=["translations"])
# the locale set is a shop setting in the dashboard, so it keeps the /settings URL
locales_router = APIRouter(prefix="/settings/locales", tags=["settings"])


@router.get("", response_model=TranslationEntryListResponse)
@inject
async def list_translations(
    use_case: FromDishka[ListTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationEntryListResponse:
    entries = await use_case(actor)
    items = [
        TranslationEntryResponse.model_validate(entry, from_attributes=True) for entry in entries
    ]
    return TranslationEntryListResponse(items=items, total=len(items))


@router.get("/export", response_model=TranslationsExportResponse)
@inject
async def export_translations(
    use_case: FromDishka[ExportTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationsExportResponse:
    return TranslationsExportResponse.model_validate(await use_case(actor), from_attributes=True)


@router.post(
    "/actions/import", response_model=TranslationsImportResponse, responses=error_responses(400)
)
@inject
async def import_translations(
    payload: TranslationsImportRequest,
    use_case: FromDishka[ImportTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationsImportResponse:
    result = await use_case(
        actor,
        TranslationsImportDto(
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
    return TranslationsImportResponse.model_validate(result, from_attributes=True)


@router.post("/actions/reset-all", response_model=TranslationEntryListResponse)
@inject
async def reset_all_translations(
    use_case: FromDishka[ResetAllTranslationsUseCase],
    actor: Actor = Depends(require_admin),
) -> TranslationEntryListResponse:
    entries = await use_case(actor)
    items = [
        TranslationEntryResponse.model_validate(entry, from_attributes=True) for entry in entries
    ]
    return TranslationEntryListResponse(items=items, total=len(items))


@router.put(
    "/{locale}/{message_id}",
    response_model=TranslationEntryResponse,
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
) -> TranslationEntryResponse:
    entry = await use_case(
        actor,
        UpdateTranslationDto(
            locale=locale, message_id=message_id, attribute_id=attribute_id, value=payload.value
        ),
    )
    return TranslationEntryResponse.model_validate(entry, from_attributes=True)


@router.post(
    "/{locale}/{message_id}/actions/reset",
    response_model=TranslationEntryResponse,
    responses=error_responses(404),
)
@inject
async def reset_translation(
    locale: Locale,
    message_id: str,
    use_case: FromDishka[ResetTranslationUseCase],
    actor: Actor = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> TranslationEntryResponse:
    entry = await use_case(
        actor,
        ResetTranslationDto(locale=locale, message_id=message_id, attribute_id=attribute_id),
    )
    return TranslationEntryResponse.model_validate(entry, from_attributes=True)


@locales_router.get("", response_model=ActiveLocalesResponse)
@inject
async def list_locales(
    use_case: FromDishka[ListActiveLocalesUseCase],
    actor: Actor = Depends(require_admin),
) -> ActiveLocalesResponse:
    return ActiveLocalesResponse.model_validate(await use_case(actor), from_attributes=True)


@locales_router.patch("", response_model=ActiveLocalesResponse, responses=error_responses(400))
@inject
async def update_locales(
    payload: UpdateLocalesRequest,
    use_case: FromDishka[SetDefaultLocaleUseCase],
    actor: Actor = Depends(require_admin),
) -> ActiveLocalesResponse:
    return ActiveLocalesResponse.model_validate(
        await use_case(actor, payload.default), from_attributes=True
    )


@locales_router.put("/{locale}", response_model=ActiveLocalesResponse)
@inject
async def add_locale(
    locale: Locale,
    use_case: FromDishka[AddLocaleUseCase],
    actor: Actor = Depends(require_admin),
) -> ActiveLocalesResponse:
    return ActiveLocalesResponse.model_validate(await use_case(actor, locale), from_attributes=True)


@locales_router.delete(
    "/{locale}", response_model=ActiveLocalesResponse, responses=error_responses(400)
)
@inject
async def remove_locale(
    locale: Locale,
    use_case: FromDishka[RemoveLocaleUseCase],
    actor: Actor = Depends(require_admin),
) -> ActiveLocalesResponse:
    return ActiveLocalesResponse.model_validate(await use_case(actor, locale), from_attributes=True)
