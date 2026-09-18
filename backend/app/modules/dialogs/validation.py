from app.core.enums import ButtonLinkType, DialogWindowKind
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto


def validate_url_value(url_value: str) -> None:
    for name in catalog.URL_VARIABLE_RE.findall(url_value):
        if name not in catalog.variable_keys():
            raise ValidationError(f"Unknown URL variable: {name}")
    literal = catalog.URL_VARIABLE_RE.sub("", url_value)
    if literal and not literal.startswith(catalog.URL_SCHEMES):
        raise ValidationError(f"URL must start with one of: {', '.join(catalog.URL_SCHEMES)}")


def validate_buttons(
    buttons: list[DialogButtonInputDto],
    *,
    window_key: str,
    window_kind: DialogWindowKind,
    navigable: set[str],
    seed_actions: set[str],
) -> None:
    seen: set[tuple[int, int]] = set()
    for button in buttons:
        position = (button.row, button.column)
        if position in seen:
            raise ValidationError(
                f"Two buttons at row {button.row}, column {button.column} in '{window_key}'"
            )
        seen.add(position)
        _validate_button(button, window_kind, navigable, seed_actions)


def _validate_button(
    button: DialogButtonInputDto,
    window_kind: DialogWindowKind,
    navigable: set[str],
    seed_actions: set[str],
) -> None:
    if button.visibility_condition and button.visibility_condition not in catalog.condition_keys():
        raise ValidationError(f"Unknown visibility condition: {button.visibility_condition}")
    if button.link_type == ButtonLinkType.ACTION:
        if window_kind == DialogWindowKind.CUSTOM:
            raise ValidationError("Custom windows cannot bind action buttons")
        if button.action_key not in catalog.action_keys():
            raise ValidationError(f"Unknown action: {button.action_key}")
        if button.action_key not in seed_actions:
            raise ValidationError(
                f"Action '{button.action_key}' is not one of this window's actions"
            )
    elif button.link_type == ButtonLinkType.NAVIGATE:
        if button.target_window_key not in navigable:
            raise ValidationError(f"Unknown target window: {button.target_window_key}")
    elif button.link_type == ButtonLinkType.URL:
        if not button.url_value:
            raise ValidationError("URL button needs a url_value")
        validate_url_value(button.url_value)
