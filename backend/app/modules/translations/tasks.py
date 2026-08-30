from dishka.integrations.taskiq import FromDishka, inject

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
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
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        await repository.delete_locale(Locale(locale))
