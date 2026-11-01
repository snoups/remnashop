from app.core.enums import LegalDocumentKind, Locale
from app.modules.legal.templates import LEGAL_TEMPLATES
from app.modules.legal.usecases.set_legal_text import MAX_MESSAGE_LENGTH, MAX_TITLE_LENGTH


def test_every_document_has_a_ru_and_en_template() -> None:
    keys = [(template.kind, template.locale) for template in LEGAL_TEMPLATES]

    assert sorted(keys) == sorted(
        (kind, locale) for kind in LegalDocumentKind for locale in (Locale.RU, Locale.EN)
    )


def test_templates_fit_the_save_limits() -> None:
    for template in LEGAL_TEMPLATES:
        assert template.title.strip() and template.body.strip()
        assert len(template.title) <= MAX_TITLE_LENGTH
        assert len(f"# {template.title}\n\n{template.body}") <= MAX_MESSAGE_LENGTH
