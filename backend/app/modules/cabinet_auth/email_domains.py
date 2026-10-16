from app.core.utils.email import normalize_email
from app.modules.settings import CabinetAuthSettingsDto


def is_allowed_domain(email: str, settings: CabinetAuthSettingsDto) -> bool:
    if not settings.restrict_email_domains:
        return True
    return normalize_email(email).rpartition("@")[2] in settings.allowed_email_domains
