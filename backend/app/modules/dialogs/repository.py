from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CUSTOM_DIALOG_WINDOW_SLOTS
from app.core.db.models import DialogButton, DialogWindow
from app.core.enums import BannerName, ButtonLinkType, ButtonStyleKind, DialogFlow, DialogWindowKind
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.dialogs.dto import (
    CreateCustomWindowDto,
    DialogButtonDto,
    DialogButtonInputDto,
    DialogWindowDto,
    UpdateDialogWindowDto,
)


def _optional_enum(value: Optional[str], enum: type) -> object:
    return enum(value) if value is not None else None


class DialogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _button_to_dto(self, row: DialogButton) -> DialogButtonDto:
        return DialogButtonDto.model_validate(row, from_attributes=True)

    def _to_dto(self, row: DialogWindow) -> DialogWindowDto:
        return DialogWindowDto(
            id=row.id,
            key=row.key,
            kind=row.kind,
            flow=row.flow,
            banner_name=row.banner_name,
            is_enabled=row.is_enabled,
            position=row.position,
            slot=row.slot,
            buttons=[self._button_to_dto(b) for b in row.buttons],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_row(self, key: str) -> Optional[DialogWindow]:
        row: Optional[DialogWindow] = await self.session.scalar(
            select(DialogWindow).where(DialogWindow.key == key)
        )
        return row

    async def _get_row_or_raise(self, key: str) -> DialogWindow:
        row = await self._get_row(key)
        if row is None:
            raise NotFoundError(f"Dialog window '{key}' not found")
        return row

    async def list_all(self) -> list[DialogWindowDto]:
        result = await self.session.scalars(
            select(DialogWindow).order_by(
                DialogWindow.flow, DialogWindow.position, DialogWindow.key
            )
        )
        return [self._to_dto(row) for row in result]

    async def get_by_key(self, key: str) -> Optional[DialogWindowDto]:
        row = await self._get_row(key)
        return self._to_dto(row) if row is not None else None

    async def get_by_key_or_raise(self, key: str) -> DialogWindowDto:
        return self._to_dto(await self._get_row_or_raise(key))

    async def list_seed_keys(self) -> set[str]:
        result = await self.session.scalars(
            select(DialogWindow.key).where(DialogWindow.kind == DialogWindowKind.SEED)
        )
        return set(result)

    def _button_from_snapshot(self, window_id: int, raw: dict) -> DialogButton:
        return DialogButton(
            window_id=window_id,
            row=raw["row"],
            column=raw["column"],
            text_key=raw["text_key"],
            link_type=ButtonLinkType(raw["link_type"]),
            action_key=raw.get("action_key"),
            target_window_key=raw.get("target_window_key"),
            url_value=raw.get("url_value"),
            visibility_condition=raw.get("visibility_condition"),
            style=_optional_enum(raw.get("style"), ButtonStyleKind),
            icon_custom_emoji_id=raw.get("icon_custom_emoji_id"),
            is_hidden=raw.get("is_hidden", False),
        )

    async def upsert_seed(
        self,
        key: str,
        flow: DialogFlow,
        banner_name: Optional[BannerName],
        default_snapshot: dict,
    ) -> bool:
        if await self._get_row(key) is not None:
            return False
        window = DialogWindow(
            key=key,
            kind=DialogWindowKind.SEED,
            flow=flow,
            banner_name=banner_name,
            is_enabled=True,
            default_snapshot=default_snapshot,
        )
        self.session.add(window)
        await self.session.flush()
        for raw in default_snapshot.get("buttons", []):
            self.session.add(self._button_from_snapshot(window.id, raw))
        await self.session.flush()
        return True

    async def update_window(self, key: str, data: UpdateDialogWindowDto) -> DialogWindowDto:
        row = await self._get_row_or_raise(key)
        if data.banner_name_provided:
            row.banner_name = data.banner_name
        if data.is_enabled is not None:
            row.is_enabled = data.is_enabled
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def replace_buttons(
        self, key: str, buttons: list[DialogButtonInputDto]
    ) -> DialogWindowDto:
        # Lock the window row so two concurrent replace calls can't interleave
        # their delete/insert and leave a half-written layout. Arbitrary: the
        # window's own PK row is the natural lock granularity here.
        row = await self.session.scalar(
            select(DialogWindow).where(DialogWindow.key == key).with_for_update()
        )
        if row is None:
            raise NotFoundError(f"Dialog window '{key}' not found")
        for existing in list(row.buttons):
            await self.session.delete(existing)
        await self.session.flush()
        for button in buttons:
            self.session.add(
                DialogButton(
                    window_id=row.id,
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
            )
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def _claim_free_slot(self) -> int:
        taken = set(
            await self.session.scalars(
                select(DialogWindow.slot).where(DialogWindow.slot.is_not(None))
            )
        )
        for slot in range(CUSTOM_DIALOG_WINDOW_SLOTS):
            if slot not in taken:
                return slot
        raise ValidationError(
            f"No free dialog window slot left (limit is {CUSTOM_DIALOG_WINDOW_SLOTS})"
        )

    async def create_custom_window(self, key: str, data: CreateCustomWindowDto) -> DialogWindowDto:
        if await self._get_row(key) is not None:
            raise ConflictError(f"Dialog window '{key}' already exists")
        window = DialogWindow(
            key=key,
            kind=DialogWindowKind.CUSTOM,
            flow=DialogFlow.CUSTOM,
            banner_name=data.banner_name,
            is_enabled=True,
            position=data.position,
            slot=await self._claim_free_slot(),
            default_snapshot={"banner_name": None, "buttons": []},
        )
        self.session.add(window)
        await self.session.flush()
        await self.session.refresh(window)
        return self._to_dto(window)

    async def delete_custom_window(self, key: str) -> None:
        row = await self._get_row_or_raise(key)
        if row.kind != DialogWindowKind.CUSTOM:
            raise ValidationError("Only custom windows can be deleted")
        await self.session.delete(row)
        await self.session.flush()

    async def seed_action_keys(self, key: str) -> set[str]:
        row = await self._get_row_or_raise(key)
        return {
            b.get("action_key")
            for b in row.default_snapshot.get("buttons", [])
            if b.get("action_key")
        }

    async def reset_to_snapshot(self, key: str) -> DialogWindowDto:
        row = await self.session.scalar(
            select(DialogWindow).where(DialogWindow.key == key).with_for_update()
        )
        if row is None:
            raise NotFoundError(f"Dialog window '{key}' not found")
        if row.kind == DialogWindowKind.CUSTOM:
            raise ValidationError("Custom windows have no default to reset to; delete instead")
        snapshot = row.default_snapshot
        raw_banner = snapshot.get("banner_name")
        row.banner_name = BannerName(raw_banner) if raw_banner else None
        row.is_enabled = True
        for existing in list(row.buttons):
            await self.session.delete(existing)
        await self.session.flush()
        for raw in snapshot.get("buttons", []):
            self.session.add(self._button_from_snapshot(row.id, raw))
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)
