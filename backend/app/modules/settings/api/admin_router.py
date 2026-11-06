from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.api.uploads import MULTIPART_FILE_BODY, read_form_file
from app.core.actor import Actor
from app.core.enums import AppearanceTarget
from app.modules.settings.api.schemas import (
    AccessSettingsResponse,
    AppearanceResponse,
    BotCommandResponse,
    BotCommandsResponse,
    BotLogsResponse,
    BotRequirementsResponse,
    BotSettingsResponse,
    BotStatusResponse,
    CabinetAuthSettingsResponse,
    EmailSettingsResponse,
    OAuthSettingsResponse,
    SetBotProxyRequest,
    ShopSettingsResponse,
    UpdateAccessSettingsRequest,
    UpdateAppearanceRequest,
    UpdateBotCommandsRequest,
    UpdateBotCommandsResponse,
    UpdateBotRequirementsRequest,
    UpdateBotSettingsRequest,
    UpdateCabinetAuthSettingsRequest,
    UpdateEmailSettingsRequest,
    UpdateOAuthSettingsRequest,
    UpdateShopSettingsRequest,
)
from app.modules.settings.appearance_images import MAX_APPEARANCE_IMAGE_SIZE_BYTES
from app.modules.settings.dto import (
    GetBotCommandsDto,
    SetBotProxyDto,
    UpdateAccessSettingsDto,
    UpdateAppearanceSettingsDto,
    UpdateBotCommandsDto,
    UpdateBotRequirementsDto,
    UpdateBotSettingsDto,
    UpdateCabinetAuthSettingsDto,
    UpdateEmailSettingsDto,
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
    GetCabinetAuthSettingsUseCase,
    GetEmailSettingsUseCase,
    GetOAuthSettingsUseCase,
    GetShopSettingsUseCase,
    RemoveBotProxyUseCase,
    ResetAppearanceSettingsUseCase,
    ResetBulkEmailSettingsUseCase,
    ResetEmailSettingsUseCase,
    RestartBotUseCase,
    SetBotProxyUseCase,
    UpdateAccessSettingsUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotRequirementsUseCase,
    UpdateBotSettingsUseCase,
    UpdateCabinetAuthSettingsUseCase,
    UpdateEmailSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UpdateShopSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceLogoUseCase,
)

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
    settings = await use_case(actor, SetBotProxyDto(proxy_url=payload.proxy_url))
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
            channel_required=payload.channel_required,
            channel_id=payload.channel_id,
            channel_url=str(payload.channel_url) if payload.channel_url else None,
            trial_channel_guard=payload.trial_channel_guard,
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


@router.get("/email", response_model=EmailSettingsResponse)
@inject
async def get_email_settings(
    use_case: FromDishka[GetEmailSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> EmailSettingsResponse:
    settings = await use_case(actor)
    return EmailSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/email", response_model=EmailSettingsResponse)
@inject
async def update_email_settings(
    payload: UpdateEmailSettingsRequest,
    use_case: FromDishka[UpdateEmailSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> EmailSettingsResponse:
    settings = await use_case(
        actor,
        UpdateEmailSettingsDto(
            host=payload.host,
            port=payload.port,
            security=payload.security,
            username=payload.username,
            password=payload.password,
            from_address=payload.from_address,
            from_name=payload.from_name,
            rate_per_minute=payload.rate_per_minute,
            bulk_host=payload.bulk_host,
            bulk_port=payload.bulk_port,
            bulk_security=payload.bulk_security,
            bulk_username=payload.bulk_username,
            bulk_password=payload.bulk_password,
            bulk_from_address=payload.bulk_from_address,
            bulk_from_name=payload.bulk_from_name,
            bulk_rate_per_minute=payload.bulk_rate_per_minute,
        ),
    )
    return EmailSettingsResponse.model_validate(settings, from_attributes=True)


@router.post(
    "/email/actions/reset", response_model=EmailSettingsResponse, responses=error_responses(400)
)
@inject
async def reset_email_settings(
    use_case: FromDishka[ResetEmailSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> EmailSettingsResponse:
    settings = await use_case(actor)
    return EmailSettingsResponse.model_validate(settings, from_attributes=True)


@router.post("/email/bulk/actions/reset", response_model=EmailSettingsResponse)
@inject
async def reset_bulk_email_settings(
    use_case: FromDishka[ResetBulkEmailSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> EmailSettingsResponse:
    settings = await use_case(actor)
    return EmailSettingsResponse.model_validate(settings, from_attributes=True)


@router.get("/cabinet-auth", response_model=CabinetAuthSettingsResponse)
@inject
async def get_cabinet_auth_settings(
    use_case: FromDishka[GetCabinetAuthSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> CabinetAuthSettingsResponse:
    settings = await use_case(actor)
    return CabinetAuthSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch(
    "/cabinet-auth",
    response_model=CabinetAuthSettingsResponse,
    responses=error_responses(400),
)
@inject
async def update_cabinet_auth_settings(
    payload: UpdateCabinetAuthSettingsRequest,
    use_case: FromDishka[UpdateCabinetAuthSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> CabinetAuthSettingsResponse:
    settings = await use_case(
        actor,
        UpdateCabinetAuthSettingsDto(
            telegram_enabled=payload.telegram_enabled,
            telegram_deeplink_enabled=payload.telegram_deeplink_enabled,
            telegram_oauth_enabled=payload.telegram_oauth_enabled,
            google_enabled=payload.google_enabled,
            yandex_enabled=payload.yandex_enabled,
            email_enabled=payload.email_enabled,
            restrict_email_domains=payload.restrict_email_domains,
            allowed_email_domains=payload.allowed_email_domains,
            captcha_enabled=payload.captcha_enabled,
            captcha_provider=payload.captcha_provider,
            captcha_site_key=payload.captcha_site_key,
            captcha_secret_key=payload.captcha_secret_key,
        ),
    )
    return CabinetAuthSettingsResponse.model_validate(settings, from_attributes=True)


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
    commands = await use_case(actor, GetBotCommandsDto(default_order=default_order))
    return BotCommandsResponse(
        commands=[
            BotCommandResponse.model_validate(item, from_attributes=True) for item in commands
        ]
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
        UpdateBotCommandsDto(commands=[(item.command, item.enabled) for item in payload.commands]),
    )
    return UpdateBotCommandsResponse.model_validate(result, from_attributes=True)


@router.get("/oauth", response_model=OAuthSettingsResponse)
@inject
async def get_oauth_settings(
    use_case: FromDishka[GetOAuthSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> OAuthSettingsResponse:
    settings = await use_case(actor)
    return OAuthSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/oauth", response_model=OAuthSettingsResponse, responses=error_responses(400))
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
            google_client_id=payload.google_client_id,
            google_client_secret=payload.google_client_secret,
            yandex_client_id=payload.yandex_client_id,
            yandex_client_secret=payload.yandex_client_secret,
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
    return OAuthSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/appearance/{target}", response_model=AppearanceResponse)
@inject
async def update_appearance_settings(
    target: AppearanceTarget,
    payload: UpdateAppearanceRequest,
    use_case: FromDishka[UpdateAppearanceSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    settings = await use_case(
        actor,
        UpdateAppearanceSettingsDto(
            target=target,
            brand_name=payload.brand_name,
            primary_color=payload.primary_color,
            shader_palette=payload.shader_palette,
            shader_enabled=payload.shader_enabled,
        ),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.post("/appearance/{target}/actions/reset", response_model=AppearanceResponse)
@inject
async def reset_appearance_settings(
    target: AppearanceTarget,
    use_case: FromDishka[ResetAppearanceSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    settings = await use_case(actor, target)
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.put(
    "/appearance/{target}/logo",
    response_model=AppearanceResponse,
    responses=error_responses(400),
    openapi_extra=MULTIPART_FILE_BODY,
)
@inject
async def upload_appearance_logo(
    target: AppearanceTarget,
    use_case: FromDishka[UploadAppearanceLogoUseCase],
    request: Request,
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    file = await read_form_file(request, MAX_APPEARANCE_IMAGE_SIZE_BYTES)
    settings = await use_case(
        actor,
        UploadAppearanceImageDto(target=target, content_type=file.content_type, data=file.data),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.delete(
    "/appearance/{target}/logo", response_model=AppearanceResponse, responses=error_responses(404)
)
@inject
async def delete_appearance_logo(
    target: AppearanceTarget,
    use_case: FromDishka[DeleteAppearanceLogoUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    return AppearanceResponse.model_validate(await use_case(actor, target), from_attributes=True)


@router.put(
    "/appearance/{target}/favicon",
    response_model=AppearanceResponse,
    responses=error_responses(400),
    openapi_extra=MULTIPART_FILE_BODY,
)
@inject
async def upload_appearance_favicon(
    target: AppearanceTarget,
    use_case: FromDishka[UploadAppearanceFaviconUseCase],
    request: Request,
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    file = await read_form_file(request, MAX_APPEARANCE_IMAGE_SIZE_BYTES)
    settings = await use_case(
        actor,
        UploadAppearanceImageDto(target=target, content_type=file.content_type, data=file.data),
    )
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.delete(
    "/appearance/{target}/favicon",
    response_model=AppearanceResponse,
    responses=error_responses(404),
)
@inject
async def delete_appearance_favicon(
    target: AppearanceTarget,
    use_case: FromDishka[DeleteAppearanceFaviconUseCase],
    actor: Actor = Depends(require_admin),
) -> AppearanceResponse:
    return AppearanceResponse.model_validate(await use_case(actor, target), from_attributes=True)
