from app.core.enums import ButtonLinkType, DialogFlow, DialogWindowKind
from app.modules.dialogs.dto import DialogButtonDto, DialogWindowDto


def test_window_dto_defaults() -> None:
    dto = DialogWindowDto(key="menu.main", kind=DialogWindowKind.SEED, flow=DialogFlow.MENU)
    assert dto.is_enabled is True
    assert dto.buttons == []
    assert dto.banner_name is None


def test_button_dto_url_link() -> None:
    dto = DialogButtonDto(
        window_id=1,
        row=0,
        column=0,
        text_key="k",
        link_type=ButtonLinkType.URL,
        url_value="https://x",
    )
    assert dto.is_hidden is False
    assert dto.style is None
