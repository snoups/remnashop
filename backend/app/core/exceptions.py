from datetime import datetime


class PermissionDeniedError(Exception): ...


class ConflictError(Exception): ...


class AuthenticationError(Exception): ...


class NotFoundError(Exception): ...


class ValidationError(Exception): ...


class CooldownError(Exception):
    def __init__(self, available_at: datetime) -> None:
        self.available_at = available_at
        super().__init__(f"Cooldown active until {available_at}")


class RemnawavePanelUnavailableError(Exception): ...


class PaymentGatewayError(Exception): ...
