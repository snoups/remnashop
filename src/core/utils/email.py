from email_validator import EmailNotValidError, validate_email


def is_valid_email(value: str) -> bool:
    s = value.strip()
    if not s:
        return False
    try:
        validate_email(s, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True
