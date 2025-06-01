# Constants for the application
from datetime import timezone

API_V1: str = "/api/v1"
WEBHOOK_PATH: str = "/webhook"
HEADER_SECRET_TOKEN: str = "x-telegram-bot-api-secret-token"
TIMEZONE = timezone.utc

# Resource file names for i18n
RESOURCE_I18N = ["messages.ftl", "buttons.ftl", "notifications.ftl", "popups.ftl"]

# Keys for aiogram data
MIDDLEWARE_DATA_KEY = "middleware_data"
USER_KEY = "user"
USER_SERVICE_KEY = "user_service"
THROTTLING_KEY = "throttling_key"
I18N_MIDDLEWARE_KEY = "i18n_middleware"
SESSION_POOL_KEY = "session_pool"
I18N_FORMAT_KEY = "i18n_format"
CONFIG_KEY = "config"
