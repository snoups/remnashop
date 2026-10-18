from app.modules.broadcasts.content import render_text, used_variables


def test_used_variables_accepts_spacing_variants() -> None:
    text = "Hi { $name }, {$plan} and {  $days_left  }"
    assert used_variables(text) == {"name", "plan", "days_left"}


def test_render_escapes_values_and_keeps_markup() -> None:
    result = render_text("<b>Hi { $name }</b>", {"name": "<b>Bob & Co"})
    assert result == "<b>Hi &lt;b&gt;Bob &amp; Co</b>"


def test_render_unknown_value_becomes_dash() -> None:
    assert render_text("{ $plan }", {}) == "—"


def test_render_converts_premium_emoji() -> None:
    assert render_text("[🔥](emoji:42) go", {}) == '<tg-emoji emoji-id="42">🔥</tg-emoji> go'


def test_render_escapes_emoji_like_names() -> None:
    result = render_text("{ $name }", {"name": "[🔥](emoji:1)"})
    assert result == "[🔥](emoji:1)"
