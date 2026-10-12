from typing import Any, Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Locale
from app.modules.dialogs import catalog
from app.modules.dialogs.api.schemas import (
    CreateCustomWindowRequest,
    DialogButtonInput,
    DialogCatalogResponse,
    DialogExportPayload,
    DialogTextResponse,
    DialogWindowListResponse,
    DialogWindowResponse,
    ReplaceButtonsRequest,
    UpdateDialogTextRequest,
    UpdateDialogWindowRequest,
)
from app.modules.dialogs.dto import (
    ConfigureDialogWindowDto,
    CreateCustomDialogWindowDto,
    DialogButtonInputDto,
    DialogExportDto,
    DialogTextExportDto,
    DialogWindowDto,
    DialogWindowExportDto,
    UpdateDialogTextDto,
    UpdateDialogWindowButtonsDto,
)
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    ExportDialogsUseCase,
    GetDialogCatalogUseCase,
    ImportDialogsUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogTextUseCase,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowUseCase,
)

router = APIRouter(prefix="/dialogs", tags=["dialogs"])

_KEY_PATH: Final[Any] = Path(pattern=r"^[a-z0-9._-]+$", max_length=128)


def _to_window_response(window: DialogWindowDto) -> DialogWindowResponse:
    return DialogWindowResponse.model_validate(
        {**dict(window), "text_keys": list(catalog.window_text_keys(window.key))},
        from_attributes=True,
    )


def _to_button_input(button: DialogButtonInput) -> DialogButtonInputDto:
    return DialogButtonInputDto(
        row=button.row,
        column=button.column,
        text_key=button.text_key,
        link_type=button.link_type,
        style=button.style,
        visibility_condition=button.visibility_condition,
        action_key=button.action_key,
        target_window_key=button.target_window_key,
        url_value=button.url_value,
        is_hidden=button.is_hidden,
    )


@router.get("/catalog", response_model=DialogCatalogResponse)
@inject
async def get_dialog_catalog(
    use_case: FromDishka[GetDialogCatalogUseCase],
    actor: Actor = Depends(require_admin),
) -> DialogCatalogResponse:
    return DialogCatalogResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get("/windows", response_model=DialogWindowListResponse)
@inject
async def list_dialog_windows(
    use_case: FromDishka[ListDialogWindowsUseCase],
    actor: Actor = Depends(require_admin),
) -> DialogWindowListResponse:
    windows = await use_case(actor)
    items = [_to_window_response(window) for window in windows]
    return DialogWindowListResponse(items=items, total=len(items))


@router.patch(
    "/windows/{key}", response_model=DialogWindowResponse, responses=error_responses(400, 404)
)
@inject
async def update_dialog_window(
    payload: UpdateDialogWindowRequest,
    use_case: FromDishka[UpdateDialogWindowUseCase],
    actor: Actor = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    window = await use_case(
        actor,
        ConfigureDialogWindowDto(
            key=key,
            banner_name=payload.banner_name,
            banner_name_provided="banner_name" in payload.model_fields_set,
            is_enabled=payload.is_enabled,
            name=payload.name,
        ),
    )
    return _to_window_response(window)


@router.put(
    "/windows/{key}/buttons",
    response_model=DialogWindowResponse,
    responses=error_responses(400, 404),
)
@inject
async def replace_dialog_window_buttons(
    payload: ReplaceButtonsRequest,
    use_case: FromDishka[UpdateDialogWindowButtonsUseCase],
    actor: Actor = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    window = await use_case(
        actor,
        UpdateDialogWindowButtonsDto(
            key=key, buttons=[_to_button_input(button) for button in payload.buttons]
        ),
    )
    return _to_window_response(window)


@router.post(
    "/windows",
    response_model=DialogWindowResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 409),
)
@inject
async def create_custom_dialog_window(
    payload: CreateCustomWindowRequest,
    use_case: FromDishka[CreateCustomDialogWindowUseCase],
    actor: Actor = Depends(require_admin),
) -> DialogWindowResponse:
    window = await use_case(
        actor,
        CreateCustomDialogWindowDto(name=payload.name, banner_name=payload.banner_name),
    )
    return _to_window_response(window)


@router.delete(
    "/windows/{key}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(400, 404)
)
@inject
async def delete_custom_dialog_window(
    use_case: FromDishka[DeleteCustomDialogWindowUseCase],
    actor: Actor = Depends(require_admin),
    key: str = _KEY_PATH,
) -> None:
    await use_case(actor, key)


@router.post(
    "/windows/{key}/actions/reset",
    response_model=DialogWindowResponse,
    responses=error_responses(400, 404),
)
@inject
async def reset_dialog_window(
    use_case: FromDishka[ResetDialogWindowUseCase],
    actor: Actor = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    window = await use_case(actor, key)
    return _to_window_response(window)


@router.put(
    "/text/{locale}/{message_id}",
    response_model=DialogTextResponse,
    responses=error_responses(400, 404),
)
@inject
async def update_dialog_text(
    locale: Locale,
    message_id: str,
    payload: UpdateDialogTextRequest,
    use_case: FromDishka[UpdateDialogTextUseCase],
    actor: Actor = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> DialogTextResponse:
    entry = await use_case(
        actor,
        UpdateDialogTextDto(
            locale=locale,
            message_id=message_id,
            attribute_id=attribute_id,
            value=payload.value,
        ),
    )
    return DialogTextResponse.model_validate(entry, from_attributes=True)


@router.get("/export", response_model=DialogExportPayload)
@inject
async def export_dialogs(
    use_case: FromDishka[ExportDialogsUseCase],
    actor: Actor = Depends(require_admin),
) -> DialogExportPayload:
    export = await use_case(actor)
    return DialogExportPayload.model_validate(export, from_attributes=True)


@router.post(
    "/actions/import", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(400, 404)
)
@inject
async def import_dialogs(
    payload: DialogExportPayload,
    use_case: FromDishka[ImportDialogsUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(
        actor,
        DialogExportDto(
            version=payload.version,
            windows=[
                DialogWindowExportDto(
                    key=window.key,
                    kind=window.kind,
                    banner_name=window.banner_name,
                    name=window.name,
                    is_enabled=window.is_enabled,
                    position=window.position,
                    buttons=[_to_button_input(button) for button in window.buttons],
                )
                for window in payload.windows
            ],
            texts=[
                DialogTextExportDto(
                    locale=text.locale,
                    message_id=text.message_id,
                    attribute_id=text.attribute_id,
                    value=text.value,
                )
                for text in payload.texts
            ],
        ),
    )


@router.post("/actions/reset-all", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_all_dialogs(
    use_case: FromDishka[ResetAllDialogsUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)
