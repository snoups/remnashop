from app.core.enums import AppearanceTarget
from app.modules.email import EmailBrandDto, load_email_brand, render_email, render_email_html
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateAppearanceSettingsDto


def test_layout_escapes_and_links_only_to_the_cabinet() -> None:
    text, html = render_email(
        brand="Shop <b>",
        color="#ff0000",
        has_logo=True,
        title="Hi <script>",
        body="Line 1\nLine 2 & more",
        cabinet_url="https://cabinet.example.com",
        button="Open cabinet",
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Shop &lt;b&gt;" in html
    assert 'src="cid:logo"' in html
    assert "Line 1<br>Line 2 &amp; more" in html
    assert 'href="https://cabinet.example.com"' in html
    assert html.count("href=") == 1
    assert "Hi <script>" in text and "https://cabinet.example.com" in text


def test_layout_without_logo_or_cabinet() -> None:
    _, html = render_email(
        brand="Shop", color=None, has_logo=False, title="T", body="B", cabinet_url=None, button=None
    )
    assert "cid:logo" not in html and "href=" not in html


def test_bad_color_is_ignored() -> None:
    _, html = render_email(
        brand="S",
        color="red;}</style><script>",
        has_logo=False,
        title="T",
        body="B",
        cabinet_url=None,
        button=None,
    )
    assert "<script>" not in html


def test_render_email_html_keeps_body_markup_and_footer() -> None:
    page = render_email_html(
        brand="Shop",
        color="#ff0000",
        has_logo=True,
        body_html="<p>Hi <b>there</b></p>",
        footer_html='<a href="https://x/u">Unsub</a>',
    )
    assert "<p>Hi <b>there</b></p>" in page
    assert 'src="cid:logo"' in page
    assert '<a href="https://x/u">Unsub</a>' in page
    assert "Shop" in page


async def test_brand_takes_the_cabinet_and_falls_back_to_the_dashboard(
    settings_repository: SettingsRepository,
) -> None:
    assert await load_email_brand(settings_repository) == EmailBrandDto(
        brand="remnashop", color=None, has_logo=False
    )

    await settings_repository.update_appearance_settings(
        UpdateAppearanceSettingsDto(
            target=AppearanceTarget.DASHBOARD, brand_name="Panel", primary_color="#111111"
        )
    )
    await settings_repository.update_appearance_settings(
        UpdateAppearanceSettingsDto(target=AppearanceTarget.CABINET, brand_name="Shop")
    )

    assert await load_email_brand(settings_repository) == EmailBrandDto(
        brand="Shop", color="#111111", has_logo=False
    )
