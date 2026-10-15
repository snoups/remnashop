from app.core.exceptions import AppError, RemnawavePanelUnavailableError


def is_infrastructure_error(error: BaseException) -> bool:
    # a domain refusal won't change on retry; a panel or network failure may
    return not isinstance(error, AppError) or isinstance(error, RemnawavePanelUnavailableError)
