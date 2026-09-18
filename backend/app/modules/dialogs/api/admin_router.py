from typing import Any, Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Locale
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.api.schemas import (
    CreateCustomWindowRequest,
    DialogButtonInput,
    DialogButtonItem,
    DialogCatalogResponse,
    DialogExportPayload,
    DialogTextExportItem,
    DialogTextResponse,
    DialogWindowExportItem,
    DialogWindowResponse,
    ReplaceButtonsRequest,
    UpdateDialogTextRequest,
    UpdateDialogWindowRequest,
)
from app.modules.dialogs.dto import (
    DialogButtonDto,
    DialogButtonInputDto,
    DialogCatalogDto,
    DialogExportDto,
    DialogTextExportDto,
    DialogWindowDto,
    DialogWindowExportDto,
)
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowInput,
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    ExportDialogsUseCase,
    GetDialogCatalogUseCase,
    ImportDialogsUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogTextInput,
    UpdateDialogTextUseCase,
    UpdateDialogWindowButtonsInput,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowInput,
    UpdateDialogWindowUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/dialogs", tags=["dialogs"])

_KEY_PATH: Final[Any] = Path(pattern=r"^[a-z0-9._-]+$", max_length=128)


def _to_button_item(button: DialogButtonDto) -> DialogButtonItem:
    return DialogButtonItem(
        id=button.id,
        row=button.row,
        column=button.column,
        text_key=button.text_key,
        icon_custom_emoji_id=button.icon_custom_emoji_id,
        style=button.style,
        visibility_condition=button.visibility_condition,
        link_type=button.link_type,
        action_key=button.action_key,
        target_window_key=button.target_window_key,
        url_value=button.url_value,
        is_hidden=button.is_hidden,
    )


def _to_window_response(window: DialogWindowDto) -> DialogWindowResponse:
    return DialogWindowResponse(
        key=window.key,
        kind=window.kind,
        flow=window.flow,
        banner_name=window.banner_name,
        is_enabled=window.is_enabled,
        position=window.position,
        text_keys=list(catalog.window_text_keys(window.key)),
        buttons=[_to_button_item(button) for button in window.buttons],
    )


def _to_catalog_response(catalog: DialogCatalogDto) -> DialogCatalogResponse:
    return DialogCatalogResponse(
        action_keys=catalog.action_keys,
        condition_keys=catalog.condition_keys,
        variable_keys=catalog.variable_keys,
        text_variable_keys=catalog.text_variable_keys,
        seed_window_keys=catalog.seed_window_keys,
        navigable_window_keys=catalog.navigable_window_keys,
        custom_window_limit=catalog.custom_window_limit,
    )


def _to_button_input(button: DialogButtonInput) -> DialogButtonInputDto:
    return DialogButtonInputDto(
        row=button.row,
        column=button.column,
        text_key=button.text_key,
        link_type=button.link_type,
        icon_custom_emoji_id=button.icon_custom_emoji_id,
        style=button.style,
        visibility_condition=button.visibility_condition,
        action_key=button.action_key,
        target_window_key=button.target_window_key,
        url_value=button.url_value,
        is_hidden=button.is_hidden,
    )


@router.get("/catalog", response_model=DialogCatalogResponse)
@inject
async def get_catalog(
    use_case: FromDishka[GetDialogCatalogUseCase],
    actor: UserDto = Depends(require_admin),
) -> DialogCatalogResponse:
    return _to_catalog_response(await use_case(actor))


@router.get("/windows", response_model=list[DialogWindowResponse])
@inject
async def list_windows(
    use_case: FromDishka[ListDialogWindowsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[DialogWindowResponse]:
    windows = await use_case(actor)
    return [_to_window_response(window) for window in windows]


@router.get("/windows/{key}", response_model=DialogWindowResponse)
@inject
async def get_window(
    use_case: FromDishka[ListDialogWindowsUseCase],
    actor: UserDto = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    windows = await use_case(actor)
    for window in windows:
        if window.key == key:
            return _to_window_response(window)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Dialog window '{key}' not found"
    )


@router.put("/windows/{key}", response_model=DialogWindowResponse)
@inject
async def update_window(
    payload: UpdateDialogWindowRequest,
    use_case: FromDishka[UpdateDialogWindowUseCase],
    actor: UserDto = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    try:
        window = await use_case(
            actor,
            UpdateDialogWindowInput(
                key=key,
                banner_name=payload.banner_name,
                banner_name_provided="banner_name" in payload.model_fields_set,
                is_enabled=payload.is_enabled,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_window_response(window)


@router.put("/windows/{key}/buttons", response_model=DialogWindowResponse)
@inject
async def replace_buttons(
    payload: ReplaceButtonsRequest,
    use_case: FromDishka[UpdateDialogWindowButtonsUseCase],
    actor: UserDto = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    try:
        window = await use_case(
            actor,
            UpdateDialogWindowButtonsInput(
                key=key, buttons=[_to_button_input(button) for button in payload.buttons]
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_window_response(window)


@router.post("/windows", response_model=DialogWindowResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_custom_window(
    payload: CreateCustomWindowRequest,
    use_case: FromDishka[CreateCustomDialogWindowUseCase],
    actor: UserDto = Depends(require_admin),
) -> DialogWindowResponse:
    try:
        window = await use_case(
            actor,
            CreateCustomDialogWindowInput(
                title_text=payload.title_text, banner_name=payload.banner_name
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_window_response(window)


@router.delete("/windows/{key}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_custom_window(
    use_case: FromDishka[DeleteCustomDialogWindowUseCase],
    actor: UserDto = Depends(require_admin),
    key: str = _KEY_PATH,
) -> None:
    try:
        await use_case(actor, key)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/windows/{key}/reset", response_model=DialogWindowResponse)
@inject
async def reset_window(
    use_case: FromDishka[ResetDialogWindowUseCase],
    actor: UserDto = Depends(require_admin),
    key: str = _KEY_PATH,
) -> DialogWindowResponse:
    try:
        window = await use_case(actor, key)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_window_response(window)


@router.put("/text/{locale}/{message_id}", response_model=DialogTextResponse)
@inject
async def update_dialog_text(
    locale: Locale,
    message_id: str,
    payload: UpdateDialogTextRequest,
    use_case: FromDishka[UpdateDialogTextUseCase],
    actor: UserDto = Depends(require_admin),
    attribute_id: str = Query(default=""),
) -> DialogTextResponse:
    try:
        entry = await use_case(
            actor,
            UpdateDialogTextInput(
                locale=locale,
                message_id=message_id,
                attribute_id=attribute_id,
                value=payload.value,
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return DialogTextResponse(
        locale=entry.locale,
        message_id=entry.message_id,
        value=entry.value,
        default_value=entry.default_value,
    )


@router.get("/export", response_model=DialogExportPayload)
@inject
async def export_dialogs(
    use_case: FromDishka[ExportDialogsUseCase],
    actor: UserDto = Depends(require_admin),
) -> DialogExportPayload:
    export = await use_case(actor)
    return DialogExportPayload(
        version=export.version,
        windows=[
            DialogWindowExportItem(
                key=window.key,
                kind=window.kind,
                banner_name=window.banner_name,
                is_enabled=window.is_enabled,
                position=window.position,
                buttons=[
                    DialogButtonInput(
                        row=button.row,
                        column=button.column,
                        text_key=button.text_key,
                        link_type=button.link_type,
                        icon_custom_emoji_id=button.icon_custom_emoji_id,
                        style=button.style,
                        visibility_condition=button.visibility_condition,
                        action_key=button.action_key,
                        target_window_key=button.target_window_key,
                        url_value=button.url_value,
                        is_hidden=button.is_hidden,
                    )
                    for button in window.buttons
                ],
            )
            for window in export.windows
        ],
        texts=[
            DialogTextExportItem(
                locale=text.locale,
                message_id=text.message_id,
                attribute_id=text.attribute_id,
                value=text.value,
            )
            for text in export.texts
        ],
    )


@router.post("/import", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def import_dialogs(
    payload: DialogExportPayload,
    use_case: FromDishka[ImportDialogsUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(
            actor,
            DialogExportDto(
                version=payload.version,
                windows=[
                    DialogWindowExportDto(
                        key=window.key,
                        kind=window.kind,
                        banner_name=window.banner_name,
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
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_all(
    use_case: FromDishka[ResetAllDialogsUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    await use_case(actor)
