from unittest.mock import AsyncMock, MagicMock

from app.core.enums import Locale
from app.modules.broadcasts.render import load_unsubscribe_labels
from tests.seeded_translations import seeded_fluent_source


async def test_unsubscribe_labels_come_from_each_locale() -> None:
    repository = MagicMock()
    repository.get_fluent_text_by_locale = AsyncMock(
        return_value={
            Locale.RU: seeded_fluent_source(Locale.RU),
            # a locale without the key is left to the caller's fallback
            Locale.EN: "other = Other\n",
        }
    )

    labels = await load_unsubscribe_labels(repository, [Locale.RU, Locale.EN])

    assert labels == {Locale.RU: "Отписаться от рассылки"}
