from typing import Final

from src.application.common import Interactor

from .commands.commit import CommitPromocode
from .commands.delete import DeletePromocode

PROMOCODE_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    CommitPromocode,
    DeletePromocode,
)
