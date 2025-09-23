from typing import Any

from pydantic import SecretStr
from pydantic_core.core_schema import FieldValidationInfo


def validate_not_change_me(value: Any, info: FieldValidationInfo) -> Any:
    current_value: str

    if isinstance(value, SecretStr):
        current_value = value.get_secret_value()

    env_prefix = info.config.get("env_prefix", "") if info.config else ""
    field_name = info.field_name.upper() if info.field_name else "UNKNOWN_FIELD"
    full_env_var_name = f"{env_prefix}{field_name}"

    if not current_value or current_value.strip().lower() == "change_me":
        raise ValueError(f"{full_env_var_name} must be set and not equal to 'change_me'")

    return value
