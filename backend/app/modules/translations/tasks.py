from dishka.integrations.taskiq import FromDishka, inject

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.settings import SettingsRepository
from app.modules.translations.repository import TranslationsRepository
from app.worker.broker import broker


@broker.task
@inject(patch_module=True)
async def copy_locale_translations_task(
    source: str,
    target: str,
    repository: FromDishka[TranslationsRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        await repository.copy_locale_from(Locale(source), Locale(target))


@broker.task
@inject(patch_module=True)
async def delete_locale_translations_task(
    locale: str,
    repository: FromDishka[TranslationsRepository],
    settings_repository: FromDishka[SettingsRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    target = Locale(locale)
    async with uow:
        # Deactivate->reactivate in quick succession can queue this delete
        # after a later copy_locale_translations_task already repopulated the
        # locale -- re-check current state instead of trusting task order.
        if target in await settings_repository.list_active_locales():
            return
        await repository.delete_locale(target)
