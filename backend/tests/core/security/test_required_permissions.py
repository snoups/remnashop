import pytest

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.usecases.delete_banner import DeleteBannerUseCase
from app.modules.banners.usecases.get_banner_image import GetBannerImageUseCase
from app.modules.banners.usecases.upload_banner import UploadBannerUseCase
from app.modules.gateways.usecases.list_gateways import ListGatewaysUseCase
from app.modules.gateways.usecases.reorder_gateways import ReorderGatewaysUseCase
from app.modules.gateways.usecases.toggle_gateway_active import ToggleGatewayActiveUseCase
from app.modules.gateways.usecases.update_gateway_settings import UpdateGatewaySettingsUseCase
from app.modules.settings.usecases.add_locale import AddLocaleUseCase
from app.modules.settings.usecases.get_bot_commands import GetBotCommandsUseCase
from app.modules.settings.usecases.remove_locale import RemoveLocaleUseCase
from app.modules.translations.usecases.reset_translation import ResetTranslationUseCase
from app.modules.translations.usecases.update_translation import UpdateTranslationUseCase


@pytest.mark.parametrize(
    ("usecase_class", "expected_permission"),
    [
        (UploadBannerUseCase, Permission.BANNERS_UPLOAD),
        (DeleteBannerUseCase, Permission.BANNERS_DELETE),
        (GetBannerImageUseCase, Permission.BANNERS_IMAGE_VIEW),
        (GetBotCommandsUseCase, Permission.BOT_COMMANDS_VIEW),
        (AddLocaleUseCase, Permission.LOCALES_ADD),
        (RemoveLocaleUseCase, Permission.LOCALES_REMOVE),
        (UpdateTranslationUseCase, Permission.TRANSLATIONS_UPDATE),
        (ResetTranslationUseCase, Permission.TRANSLATIONS_RESET),
        (ListGatewaysUseCase, Permission.GATEWAYS_VIEW),
        (UpdateGatewaySettingsUseCase, Permission.GATEWAYS_UPDATE),
        (ToggleGatewayActiveUseCase, Permission.GATEWAYS_TOGGLE),
        (ReorderGatewaysUseCase, Permission.GATEWAYS_REORDER),
    ],
)
def test_split_usecase_requires_expected_permission(
    usecase_class: type[UseCase], expected_permission: Permission
) -> None:
    assert usecase_class.required_permission == expected_permission
