from typing import Final

from src.application.common.interactor import Interactor

from .commands.configuration import (
    MovePaymentGatewayUp,
    TogglePaymentGatewayActive,
    ToggleYooKassaRequestEmail,
    UpdatePaymentGatewaySettings,
)
from .commands.payment import (
    CreateDefaultPaymentGateway,
    CreatePayment,
    CreateTestPayment,
    ProcessPayment,
)
from .queries.providers import GetPaymentGatewayInstance

GATEWAYS_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    GetPaymentGatewayInstance,
    MovePaymentGatewayUp,
    TogglePaymentGatewayActive,
    ToggleYooKassaRequestEmail,
    UpdatePaymentGatewaySettings,
    CreateDefaultPaymentGateway,
    CreatePayment,
    CreateTestPayment,
    ProcessPayment,
)
