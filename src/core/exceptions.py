from typing import Union


class MenuRenderError(Exception): ...


class PermissionDeniedError(Exception): ...


class UserNotFoundError(Exception):
    def __init__(self, user_telegram_id: Union[int, str, None] = None) -> None:
        self.user_telegram_id = user_telegram_id
        super().__init__(
            f"User with id '{user_telegram_id}' not found" if user_telegram_id else "User not found"
        )


class FileNotFoundError(Exception): ...


class LogsToFileDisabledError(Exception):
    def __init__(self) -> None:
        super().__init__("Logging to file is disabled in configuration")


class PlanError(Exception): ...


class SquadsEmptyError(PlanError): ...


class TrialDurationError(PlanError): ...


class PlanNameAlreadyExistsError(PlanError): ...


class UserAlreadyAllowedError(PlanError): ...


class DurationAlreadyExistsError(PlanError): ...


class GatewayNotConfiguredError(Exception): ...


class PurchaseError(Exception): ...


class TrialError(Exception): ...


class MenuEditorInvalidPayloadError(Exception): ...
