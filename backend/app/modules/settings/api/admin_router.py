from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.settings.api.schemas import (
    AccessSettingsResponse,
    AppearanceResponse,
    BotCommandItem,
    BotCommandsResponse,
    BotLogsResponse,
    BotRequirementsResponse,
    BotSettingsResponse,
    BotStatusResponse,
    OAuthSettingsResponse,
    SetBotProxyRequest,
    ShopSettingsResponse,
    UpdateAccessSettingsRequest,
    UpdateAppearanceRequest,
    UpdateBotCommandsRequest,
    UpdateBotCommandsResponse,
    UpdateBotRequirementsRequest,
    UpdateBotSettingsRequest,
    UpdateOAuthSettingsRequest,
    UpdateShopSettingsRequest,
)
from app.modules.settings.dto import (
    UpdateAccessSettingsDto,
    UpdateAppearanceSettingsDto,
    UpdateBotRequirementsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
    UpdateShopSettingsDto,
    UploadAppearanceImageDto,
)
from app.modules.settings.usecases import (
    DeleteAppearanceFaviconUseCase,
    DeleteAppearanceLogoUseCase,
    GetAccessSettingsUseCase,
    GetBotCommandsUseCase,
    GetBotLogsUseCase,
    GetBotRequirementsUseCase,
    GetBotSettingsUseCase,
    GetBotStatusUseCase,
    GetOAuthSettingsUseCase,
    GetShopSettingsUseCase,
    RemoveBotProxyUseCase,
    ResetAppearanceSettingsUseCase,
    RestartBotUseCase,
    SetBotProxyUseCase,
    UpdateAccessSettingsUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotRequirementsUseCase,
    UpdateBotSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UpdateShopSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceLogoUseCase,
)
from app.modules.settings.usecases.upload_appearance_image import MAX_APPEARANCE_IMAGE_SIZE_BYTES

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/bot", response_model=BotSettingsResponse)
@inject
async def get_bot_settings(
    use_case: FromDishka[GetBotSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BotSettingsResponse:
    settings = await use_case(actor)
    return BotSettingsResponse.model_validate(settings, from_attributes=True)


@router.get("/bot/status", response_model=BotStatusResponse)
@inject
async def get_bot_status(
    use_case: FromDishka[GetBotStatusUseCase],
    actor: Actor = Depends(require_admin),
) -> BotStatusResponse:
    status = await use_case(actor)
    return BotStatusResponse.model_validate(status, from_attributes=True)


@router.get("/bot/logs", response_model=BotLogsResponse)
@inject
async def get_bot_logs(
    use_case: FromDishka[GetBotLogsUseCase],
    actor: Actor = Depends(require_admin),
) -> BotLogsResponse:
    return BotLogsResponse(lines=await use_case(actor))


@router.patch("/bot", response_model=BotSettingsResponse)
@inject
async def update_bot_settings(
    payload: UpdateBotSettingsRequest,
    use_case: FromDishka[UpdateBotSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BotSettingsResponse:
    settings = await use_case(
        actor,
        UpdateBotSettingsDto(
            token=payload.token,
            secret_token=payload.secret_token,
            drop_pending_updates=payload.drop_pending_updates,
        ),
    )
    return BotSettingsResponse.model_validate(settings, from_attributes=True)


@router.put("/bot/proxy", response_model=BotSettingsResponse, responses=error_responses(400))
@inject
async def set_bot_proxy(
    payload: SetBotProxyRequest,
    use_case: FromDishka[SetBotProxyUseCase],
    actor: Actor = Depends(require_admin),
) -> BotSettingsResponse:
    settings = await use_case(actor, payload.proxy_url)
    return BotSettingsResponse.model_validate(settings, from_attributes=True)


@router.delete("/bot/proxy", response_model=BotSettingsResponse)
@inject
async def remove_bot_proxy(
    use_case: FromDishka[RemoveBotProxyUseCase],
    actor: Actor = Depends(require_admin),
) -> BotSettingsResponse:
    settings = await use_case(actor)
    return BotSettingsResponse.model_validate(settings, from_attributes=True)


@router.get("/bot/requirements", response_model=BotRequirementsResponse)
@inject
async def get_bot_requirements(
    use_case: FromDishka[GetBotRequirementsUseCase],
    actor: Actor = Depends(require_admin),
) -> BotRequirementsResponse:
    settings = await use_case(actor)
    return BotRequirementsResponse.model_validate(settings, from_attributes=True)


@router.put(
    "/bot/requirements",
    response_model=BotRequirementsResponse,
    responses=error_responses(400),
)
@inject
async def update_bot_requirements(
    payload: UpdateBotRequirementsRequest,
    use_case: FromDishka[UpdateBotRequirementsUseCase],
    actor: Actor = Depends(require_admin),
) -> BotRequirementsResponse:
    settings = await use_case(
        actor,
        UpdateBotRequirementsDto(
            rules_required=payload.rules_required,
            rules_url=str(payload.rules_url) if payload.rules_url else None,
            channel_required=payload.channel_required,
            channel_id=payload.channel_id,
            channel_url=str(payload.channel_url) if payload.channel_url else None,
        ),
    )
    return BotRequirementsResponse.model_validate(settings, from_attributes=True)


@router.get("/access", response_model=AccessSettingsResponse)
@inject
async def get_access_settings(
    use_case: FromDishka[GetAccessSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AccessSettingsResponse:
    settings = await use_case(actor)
    return AccessSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/access", response_model=AccessSettingsResponse)
@inject
async def update_access_settings(
    payload: UpdateAccessSettingsRequest,
    use_case: FromDishka[UpdateAccessSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AccessSettingsResponse:
    settings = await use_case(
        actor,
        UpdateAccessSettingsDto(
            mode=payload.mode,
            registration_enabled=payload.registration_enabled,
            payments_enabled=payload.payments_enabled,
        ),
    )
    return AccessSettingsResponse.model_validate(settings, from_attributes=True)


@router.get("/shop", response_model=ShopSettingsResponse)
@inject
async def get_shop_settings(
    use_case: FromDishka[GetShopSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> ShopSettingsResponse:
    settings = await use_case(actor)
    return ShopSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/shop", response_model=ShopSettingsResponse, responses=error_responses(400))
@inject
async def update_shop_settings(
    payload: UpdateShopSettingsRequest,
    use_case: FromDishka[UpdateShopSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> ShopSettingsResponse:
    settings = await use_case(
        actor,
        UpdateShopSettingsDto(
            **payload.model_dump(exclude_unset=True),
            fields_set=frozenset(payload.model_fields_set),
        ),
    )
    return ShopSettingsResponse.model_validate(settings, from_attributes=True)


@router.post("/bot/actions/restart", status_code=status.HTTP_202_ACCEPTED)
@inject
async def restart_bot(
    use_case: FromDishka[RestartBotUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)


@router.get("/bot/commands", response_model=BotCommandsResponse)
@inject
async def get_bot_commands(
    use_case: FromDishka[GetBotCommandsUseCase],
    default_order: bool = False,
    actor: Actor = Depends(require_admin),
) -> BotCommandsResponse:
    commands = await use_case(actor, default_order)
    return BotCommandsResponse(
        commands=[BotCommandItem.model_validate(item, from_attributes=True) for item in commands]
    )


@router.put(
    "/bot/commands", response_model=UpdateBotCommandsResponse, responses=error_responses(400)
)
@inject
async def update_bot_commands(
    payload: UpdateBotCommandsRequest,
    use_case: FromDishka[UpdateBotCommandsUseCase],
    actor: Actor = Depends(require_admin),
) -> UpdateBotCommandsResponse:
    result = await use_case(
        actor,
        [(item.command, item.enabled) for item in payload.commands],
    )
    return UpdateBotCommandsResponse(
        commands=[
            BotCommandItem.model_validate(item, from_attributes=True) for item in result.commands
        ],
        telegram_sync_failed=result.telegram_sync_failed,
    )


@router.get("/oauth", response_model=OAuthSettingsResponse)
@inject
async def get_oauth_settings(
    use_case: FromDishka[GetOAuthSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> OAuthSettingsResponse:
    settings = await use_case(actor)
    return OAuthSettingsResponse(
        is_github_configured=settings.is_github_configured,
        is_github_enabled=settings.github_enabled,
        is_telegram_configured=settings.is_telegram_configured,
        is_telegram_enabled=settings.telegram_enabled,
        is_oidc_configured=settings.is_oidc_configured,
        is_oidc_enabled=settings.oidc_enabled,
        oidc_display_name=settings.oidc_display_name,
        is_password_login_enabled=settings.password_login_enabled,
        is_passkey_configured=settings.is_passkey_configured,
        is_passkey_enabled=settings.passkey_enabled,
        passkey_rp_id=settings.passkey_rp_id,
        passkey_origin=settings.passkey_origin,
    )


@router.patch("/oauth", response_model=OAuthSettingsResponse)
@inject
async def update_oauth_settings(
    payload: UpdateOAuthSettingsRequest,
    use_case: FromDishka[UpdateOAuthSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> OAuthSettingsResponse:
    settings = await use_case(
        actor,
        UpdateOAuthSettingsDto(
            github_client_id=payload.github_client_id,
            github_client_secret=payload.github_client_secret,
            github_enabled=payload.github_enabled,
            telegram_client_id=payload.telegram_client_id,
            telegram_client_secret=payload.telegram_client_secret,
            telegram_enabled=payload.telegram_enabled,
            oidc_issuer_url=payload.oidc_issuer_url,
            oidc_client_id=payload.oidc_client_id,
            oidc_client_secret=payload.oidc_client_secret,
            oidc_display_name=payload.oidc_display_name,
            oidc_enabled=payload.oidc_enabled,
            password_login_enabled=payload.password_login_enabled,
            passkey_enabled=payload.passkey_enabled,
            passkey_rp_id=payload.passkey_rp_id,
            passkey_origin=payload.passkey_origin,
        ),
    )
    return OAuthSettingsResponse(
        is_github_configured=settings.is_github_configured,
        is_github_enabled=settings.github_enabled,
        is_telegram_configured=settings.is_telegram_configured,
        is_telegram_enabled=settings.telegram_enabled,
        is_oidc_configured=settings.is_oidc_configured,
        is_oidc_enabled=settings.oidc_enabled,
        oidc_display_name=settings.oidc_display_name,
        is_password_login_enabled=settings.password_login_enabled,
        is_passkey_configured=settings.is_passkey_configured,
        is_passkey_enabled=settings.passkey_enabled,
        passkey_rp_id=settings.passkey_rp_id,
        passkey_origin=settings.passkey_origin,
    )


@router.patch("/appearance", response_model=AppearanceResponse)
@inject
async def update_appearance_settings(
    payload: UpdateAppearanceRequest,
    use_case: FromDishka[UpdateAppearanceSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    settings = await use_case(
        actor,
        UpdateAppearanceSettingsDto(
            brand_name=payload.brand_name,
            primary_color=payload.primary_color,
            shader_palette=payload.shader_palette,
            shader_enabled=payload.shader_enabled,
        ),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.post("/appearance/actions/reset", response_model=AppearanceResponse)
@inject
async def reset_appearance_settings(
    use_case: FromDishka[ResetAppearanceSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    settings = await use_case(actor)
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.put("/appearance/logo", response_model=AppearanceResponse, responses=error_responses(400))
@inject
async def upload_appearance_logo(
    use_case: FromDishka[UploadAppearanceLogoUseCase],
    file: UploadFile = File(...),
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    data = await file.read(MAX_APPEARANCE_IMAGE_SIZE_BYTES + 1)
    settings = await use_case(
        actor,
        UploadAppearanceImageDto(content_type=file.content_type or "", data=data),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.delete(
    "/appearance/logo", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_appearance_logo(
    use_case: FromDishka[DeleteAppearanceLogoUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)


@router.put(
    "/appearance/favicon", response_model=AppearanceResponse, responses=error_responses(400)
)
@inject
async def upload_appearance_favicon(
    use_case: FromDishka[UploadAppearanceFaviconUseCase],
    file: UploadFile = File(...),
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    data = await file.read(MAX_APPEARANCE_IMAGE_SIZE_BYTES + 1)
    settings = await use_case(
        actor,
        UploadAppearanceImageDto(content_type=file.content_type or "", data=data),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.delete(
    "/appearance/favicon", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_appearance_favicon(
    use_case: FromDishka[DeleteAppearanceFaviconUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)
