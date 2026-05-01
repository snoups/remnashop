import asyncio
import importlib
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog.widgets.kbd.base import Keyboard
from aiogram_dialog.widgets.text import Format

from src.telegram.widgets import I18nFormat


DIALOG_MODULES = [
    "src.telegram.routers.menu.dialog",
    "src.telegram.routers.subscription.dialog",
    "src.telegram.routers.dashboard.dialog",
    "src.telegram.routers.dashboard.statistics.dialog",
    "src.telegram.routers.dashboard.access.dialog",
    "src.telegram.routers.dashboard.broadcast.dialog",
    "src.telegram.routers.dashboard.remnawave.dialog",
    "src.telegram.routers.dashboard.remnashop.dialog",
    "src.telegram.routers.dashboard.remnashop.gateways.dialog",
    "src.telegram.routers.dashboard.remnashop.referral.dialog",
    "src.telegram.routers.dashboard.remnashop.notifications.dialog",
    "src.telegram.routers.dashboard.remnashop.plans.dialog",
    "src.telegram.routers.dashboard.remnashop.menu_editor.dialog",
    "src.telegram.routers.dashboard.users.dialog",
    "src.telegram.routers.dashboard.users.user.dialog",
    "src.telegram.routers.dashboard.importer.dialog",
]

SAMPLE_ITEMS = {
    "admins": {"telegram_id": 1143025712, "name": "Admin", "is_deletable": True},
    "availability": "OWNER",
    "buttons": {"index": 1, "text": "Кнопка меню", "is_active": True},
    "devices": {"label": "iPhone 15", "short_hwid": "preview"},
    "durations": {
        "period": "30 дней",
        "final_amount": 199,
        "discount_percent": 0,
        "original_amount": 199,
        "currency": "RUB",
        "days": 30,
    },
    "gateways": {"gateway_type": "TELEGRAM_STARS", "is_active": True},
    "payment_methods": {
        "gateway_type": "TELEGRAM_STARS",
        "final_amount": 199,
        "original_amount": 199,
        "discount_percent": 0,
        "currency": "RUB",
    },
    "plans": {"id": 1, "name": "Preview Plan"},
    "roles": "ADMIN",
    "transactions": {"id": 1, "amount": 199, "currency": "RUB"},
    "types": "URL",
    "users": {"telegram_id": 100001, "name": "Preview User"},
}


def _parse_ftl_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    out: dict[str, str] = {}

    current_base: Optional[str] = None
    current_key: Optional[str] = None
    current_buf: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_buf
        if current_key is None:
            return
        while current_buf and current_buf[-1].strip() == "":
            current_buf.pop()
        out[current_key] = "\n".join(current_buf).rstrip()
        current_key = None
        current_buf = []

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            if current_key is not None:
                current_buf.append(line)
            continue

        if not line.startswith((" ", "\t")) and "=" in line:
            flush()
            left, right = line.split("=", 1)
            current_base = left.strip()
            current_key = current_base
            value = right.lstrip()
            current_buf = [value] if value else []
            continue

        if current_base and stripped.startswith(".") and "=" in stripped:
            flush()
            left, right = stripped.split("=", 1)
            current_key = f"{current_base}.{left.strip().lstrip('.')}"
            value = right.lstrip()
            current_buf = [value] if value else []
            continue

        if current_key is not None:
            current_buf.append(line)

    flush()
    return out


def _load_ftl(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        return _parse_ftl_blocks(f.read())


@dataclass
class PreviewButton:
    text: str
    target: Optional[str] = None


@dataclass
class Screen:
    id: str
    title: str
    message_key: Optional[str]
    button_rows: list[list[PreviewButton]]
    expects_text: bool = False


class PreviewUI:
    def __init__(self) -> None:
        root = os.path.dirname(os.path.abspath(__file__))
        self._messages = _load_ftl(os.path.join(root, "..", "assets", "translations", "ru", "messages.ftl"))
        self._buttons = _load_ftl(os.path.join(root, "..", "assets", "translations", "ru", "buttons.ftl"))
        self._screens = self._build_screens()

    def _state_id(self, state: Any) -> str:
        return str(state.state).replace(":", ".")

    def _translate(self, key: str) -> str:
        return self._clean_ftl(self._buttons.get(key) or self._messages.get(key) or key)

    def _clean_ftl(self, text: str) -> str:
        selector_default = re.search(r"\*\[[^\]]+]\s*([^\n{}]+)", text)
        if selector_default:
            text = selector_default.group(1)

        text = re.sub(r"\{ *\\$[^}]+}", "Preview", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        return text.strip()

    def _text_key(self, text_widget: Any) -> Optional[str]:
        if isinstance(text_widget, I18nFormat):
            return text_widget.key
        return None

    def _text_preview(self, text_widget: Any, fallback: str) -> str:
        if isinstance(text_widget, I18nFormat):
            return self._translate(text_widget.key)

        if isinstance(text_widget, Format):
            return self._format_preview(text_widget.text)

        key = getattr(text_widget, "key", None)
        if isinstance(key, str):
            return self._translate(key)

        text = getattr(text_widget, "text", None)
        if isinstance(text, str):
            return self._format_preview(text)

        return fallback

    def _format_preview(self, template: str) -> str:
        text = template
        replacements = {
            "{item}": "Preview",
            "{item[name]}": "Preview Plan",
            "{item[label]}": "Preview Device",
            "{item[telegram_id]}": "100001",
            "{item[text]}": "Кнопка меню",
            "{item[gateway_type]}": "TELEGRAM_STARS",
            "{item[field]}": "TOKEN",
            "{duration}": "30",
            "{currency}": "RUB",
            "{gateway_type}": "TELEGRAM_STARS",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _target_for(self, widget: Keyboard) -> Optional[str]:
        state = getattr(widget, "state", None)
        if state is not None:
            return self._state_id(state)
        return None

    def _items_name(self, widget: Keyboard) -> Optional[str]:
        getter = getattr(widget, "items_getter", None)
        if getter is None:
            return None
        text = repr(getter)
        marker = "itemgetter('"
        if marker in text:
            return text.split(marker, 1)[1].split("'", 1)[0]
        return None

    def _preview_button(self, widget: Keyboard, fallback: str) -> PreviewButton:
        text_widget = getattr(widget, "text", None) or getattr(widget, "_text", None)
        label = self._text_preview(text_widget, fallback) if text_widget else fallback
        return PreviewButton(text=label, target=self._target_for(widget))

    def _walk_keyboard(self, widget: Keyboard, current_state: str) -> list[list[PreviewButton]]:
        children = list(getattr(widget, "buttons", ()) or ())
        if not children:
            return [[self._preview_button(widget, "Действие")]]

        rows: list[list[PreviewButton]] = []
        class_name = widget.__class__.__name__

        if class_name in {"Row", "Group"}:
            for child in children:
                child_rows = self._walk_keyboard(child, current_state)
                if class_name == "Row":
                    if not rows:
                        rows.append([])
                    rows[-1].extend(button for row in child_rows for button in row)
                else:
                    rows.extend(child_rows)
            return rows

        if class_name == "Column":
            for child in children:
                rows.extend(self._walk_keyboard(child, current_state))
            return rows

        if class_name == "ListGroup":
            item_name = self._items_name(widget) or "items"
            prefix = f"{item_name}: "
            for child in children:
                for row in self._walk_keyboard(child, current_state):
                    rows.append([
                        PreviewButton(prefix + button.text, button.target)
                        for button in row
                    ])
            return rows or [[PreviewButton(f"{item_name}: элемент")]]

        return [[self._preview_button(widget, "Действие")]]

    def _window_expects_text(self, window: Any) -> bool:
        on_message = getattr(window, "on_message", None)
        return bool(getattr(on_message, "inputs", None))

    def _build_screens(self) -> dict[str, Screen]:
        screens: dict[str, Screen] = {}

        for module_name in DIALOG_MODULES:
            module = importlib.import_module(module_name)
            dialog = getattr(module, "router")
            for state, window in dialog.windows.items():
                screen_id = self._state_id(state)
                keyboard = getattr(window, "keyboard", None)
                rows = self._walk_keyboard(keyboard, screen_id) if keyboard else []
                message_key = self._text_key(getattr(window, "text", None))

                screens[screen_id] = Screen(
                    id=screen_id,
                    title=screen_id,
                    message_key=message_key,
                    button_rows=rows,
                    expects_text=self._window_expects_text(window),
                )

        return screens

    def build_keyboard(self, screen: Screen) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for row in screen.button_rows:
            buttons = []
            for button in row:
                callback_data = f"pv:{button.target}" if button.target else f"pv_action:{screen.id}"
                buttons.append(InlineKeyboardButton(text=button.text, callback_data=callback_data))
            if buttons:
                builder.row(*buttons)
        return builder.as_markup()

    def render(self, screen_id: str) -> tuple[str, InlineKeyboardMarkup]:
        screen = self._screens.get(screen_id) or self._screens["MainMenu.MAIN"]
        body = self._translate(screen.message_key) if screen.message_key else screen.id
        hint = "\n\n<i>Preview: экран собран из реальных Dialog/Window. Данные подставлены заглушками.</i>"
        if screen.expects_text:
            hint += "\n<i>Можно отправить любое сообщение — оно будет принято как ввод.</i>"
        text = f"<code>{screen.id}</code>\n\n{body}{hint}"
        return text, self.build_keyboard(screen)

    def has_screen(self, screen_id: str) -> bool:
        return screen_id in self._screens

    def expects_text(self, screen_id: str) -> bool:
        screen = self._screens.get(screen_id)
        return bool(screen and screen.expects_text)


_user_screen: dict[int, str] = {}


async def main() -> None:
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN (or TELEGRAM_BOT_TOKEN)")

    ui = PreviewUI()

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        if not message.from_user:
            return
        _user_screen[message.from_user.id] = "MainMenu.MAIN"
        text, kb = ui.render("MainMenu.MAIN")
        await message.answer(text, reply_markup=kb)

    @dp.callback_query(F.data.startswith("pv_action:"))
    async def on_action(callback: CallbackQuery) -> None:
        await callback.answer("Это action-кнопка настоящего бота. В preview действие не выполняется.", show_alert=True)

    @dp.callback_query(F.data.startswith("pv:"))
    async def on_nav(callback: CallbackQuery) -> None:
        if not callback.data or not callback.from_user:
            return
        target = callback.data.removeprefix("pv:")
        if not ui.has_screen(target):
            target = "MainMenu.MAIN"
        _user_screen[callback.from_user.id] = target
        text, kb = ui.render(target)
        if callback.message:
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

    @dp.message()
    async def on_any_message(message: Message) -> None:
        if not message.from_user:
            return
        current = _user_screen.get(message.from_user.id, "MainMenu.MAIN")
        text, kb = ui.render(current)
        if ui.expects_text(current):
            await message.answer("Принято в preview.\n\n" + text, reply_markup=kb)
            return
        await message.answer(text, reply_markup=kb)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
