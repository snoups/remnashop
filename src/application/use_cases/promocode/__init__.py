from typing import Final

from src.application.common import Interactor

from .commands.management import CreatePromocode, DeactivatePromocode, RecordPromocodeActivation
from .queries.validation import GetPromocode, ValidatePromocode

PROMOCODE_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    GetPromocode,
    ValidatePromocode,
    CreatePromocode,
    DeactivatePromocode,
    RecordPromocodeActivation,
)
