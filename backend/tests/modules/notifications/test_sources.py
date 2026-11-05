from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.notifications.sources import NotificationRendererFactory
from app.modules.translations import TranslationRepository


async def test_the_renderer_is_reused_until_the_translations_change(
    translation_repository: TranslationRepository, uow: UnitOfWork
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.set_default_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "ntf-test-cache", "", "First")
    factory = NotificationRendererFactory(translation_repository, uow)

    first = await factory.build()
    assert await factory.build() is first
    assert first.render_message(Locale.EN, "ntf-test-cache", {}) == "First"

    await translation_repository.update_value(Locale.EN, "ntf-test-cache", "", "Second")
    changed = await factory.build()

    assert changed is not first
    assert changed.render_message(Locale.EN, "ntf-test-cache", {}) == "Second"
