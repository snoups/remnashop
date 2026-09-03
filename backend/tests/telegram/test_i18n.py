from app.core.config import AppConfig
from app.core.enums import Locale, Role
from app.modules.users.dto import UserDto
from app.telegram.i18n import get_translator, read_translator_hub


async def test_read_translator_hub_builds_a_working_hub(config: AppConfig) -> None:
    hub = await read_translator_hub(config)
    runner = hub.get_translator_by_locale(config.default_locale.value)
    # Any real key already seeded (commands.ftl exists in both locales) --
    # this just proves the hub resolves and Fluent parses without error.
    assert runner is not None


def test_get_translator_resolves_by_user_language() -> None:
    class _FakeHub:
        def get_translator_by_locale(self, locale: str) -> str:
            return locale

    user = UserDto(id=1, name="test", role=Role.USER, language=Locale.RU)
    result = get_translator(_FakeHub(), user)  # type: ignore[arg-type]
    assert result == "ru"
