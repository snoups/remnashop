from typing import Final

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.constants import ALEMBIC_INI

_BASE_REVISION: Final[str] = "1000"


def _scripts() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def test_chain_starts_at_the_released_baseline() -> None:
    assert _scripts().get_bases() == [_BASE_REVISION]


def test_chain_has_one_head() -> None:
    assert len(_scripts().get_heads()) == 1
