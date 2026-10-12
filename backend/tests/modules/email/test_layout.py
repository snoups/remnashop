from app.modules.email import render_email


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
