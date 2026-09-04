from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import ButtonLinkType, DialogWindowKind
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto, DialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowButtonsInput:
    key: str
    buttons: list[DialogButtonInputDto]


class UpdateDialogWindowButtonsUseCase(UseCase[UpdateDialogWindowButtonsInput, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork, redis: Redis) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._redis = redis

    async def _execute(
        self, actor: UserDto, data: UpdateDialogWindowButtonsInput
    ) -> DialogWindowDto:
        window = await self._dialog_repository.get_by_key_or_raise(data.key)
        all_windows = await self._dialog_repository.list_all()
        navigable = {w.key for w in all_windows} | {w.key for w in catalog.all_windows()}
        seed_actions = (
            await self._dialog_repository.seed_action_keys(data.key)
            if window.kind == DialogWindowKind.SEED
            else set()
        )

        seen: set[tuple[int, int]] = set()
        for button in data.buttons:
            pos = (button.row, button.column)
            if pos in seen:
                raise ValidationError(f"Two buttons at row {button.row}, column {button.column}")
            seen.add(pos)
            self._validate_button(button, window, navigable, seed_actions)

        async with self._uow:
            updated = await self._dialog_repository.replace_buttons(data.key, data.buttons)
        await publish_dialog_change(self._redis)
        return updated

    def _validate_button(
        self,
        button: DialogButtonInputDto,
        window: DialogWindowDto,
        navigable: set[str],
        seed_actions: set[str],
    ) -> None:
        if (
            button.visibility_condition
            and button.visibility_condition not in catalog.condition_keys()
        ):
            raise ValidationError(f"Unknown visibility condition: {button.visibility_condition}")
        if button.link_type == ButtonLinkType.ACTION:
            if window.kind == DialogWindowKind.CUSTOM:
                raise ValidationError("Custom windows cannot bind action buttons")
            if button.action_key not in catalog.action_keys():
                raise ValidationError(f"Unknown action: {button.action_key}")
            if button.action_key not in seed_actions:
                raise ValidationError(
                    f"Action '{button.action_key}' is not one of this window's actions"
                )
        elif button.link_type == ButtonLinkType.NAVIGATE:
            if button.target_window_key not in navigable:
                raise ValidationError(f"Unknown target window: {button.target_window_key}")
        elif button.link_type == ButtonLinkType.URL:
            if not button.url_value:
                raise ValidationError("URL button needs a url_value")
