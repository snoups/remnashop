import json
from typing import Any

import pytest

from app.modules.announcements.feed import FeedError, parse_feed


def _item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "2026-10-release-1.0.2",
        "title": {"ru": "Вышла 1.0.2", "en": "1.0.2 is out"},
        "notify_at": "2026-10-05T10:00:00Z",
    }
    item.update(overrides)
    return item


def _feed(*items: dict[str, Any]) -> bytes:
    return json.dumps({"items": list(items)}).encode()


def test_minimal_item_gets_defaults() -> None:
    [item] = parse_feed(_feed(_item()))
    assert item.icon == "info"
    assert item.severity == "info"
    assert item.roles is None and item.versions is None
    assert item.slides == [] and item.auto_open is False


def test_unknown_icon_falls_back_to_info() -> None:
    [item] = parse_feed(_feed(_item(icon="skull")))
    assert item.icon == "info"


def test_auto_open_without_slides_is_dropped() -> None:
    [item] = parse_feed(_feed(_item(auto_open=True)))
    assert item.auto_open is False


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "Has Spaces"},
        {"title": {}},
        {"notify_at": "2026-10-05T10:00:00"},  # naive datetime
        {"versions": ">=not-a-version"},
        {"versions": ">=1.0.0," + "!=1.0.0," * 30 + "!=2.0"},  # valid specifier, over 200 chars
        {"title": {"en": "a\u0000b"}},
        {"title": {"en\u0000": "x"}},
        {"slides": [{"text": {"en\u0000": "x"}}]},
        {"roles": ["USER"]},
        {"roles": []},
        {"url": "http://github.com/remnashop"},  # not https
        {"url": "https://evil.example/phish"},  # host outside allowlist
        {"url": "https://evil.example\\@github.com/x"},  # backslash
        {"url": "https://user:pass@github.com/x"},  # userinfo
        {"url": "https://github.com:444/x"},  # non-443 port
        {"url": "https://github.com/x with space"},  # whitespace
        {"slides": [{"text": {"en": "x"}, "image": "../secret.png"}]},
        {"slides": [{"text": {"en": "x"}, "image": "https://evil.example/a.png"}]},
        {"slides": [{"text": {"en": "x"}, "url": "javascript:alert(1)"}]},
        {"slides": [{"text": {"en": "x"}, "url": "https://user:pass@t.me/x"}]},  # userinfo in slide
        {"slides": [{"text": {"en": "x"}, "url": "https://t.me:444/x"}]},  # port in slide
    ],
)
def test_invalid_item_is_skipped_and_the_rest_survive(bad: dict[str, Any]) -> None:
    items = parse_feed(_feed(_item(**{"id": "broken", **bad}), _item(id="ok")))
    assert [i.id for i in items] == ["ok"]


def test_unhashable_icon_types_become_info() -> None:
    [item_list] = parse_feed(_feed(_item(id="list-icon", icon=["x"])))
    assert item_list.icon == "info"
    [item_dict] = parse_feed(_feed(_item(id="dict-icon", icon={})))
    assert item_dict.icon == "info"
    [item_int] = parse_feed(_feed(_item(id="int-icon", icon=5)))
    assert item_int.icon == "info"


def test_duplicate_id_keeps_the_first() -> None:
    items = parse_feed(_feed(_item(icon="gift"), _item(icon="warning")))
    assert len(items) == 1 and items[0].icon == "gift"


def test_slide_image_path_and_allowlisted_link_pass() -> None:
    [item] = parse_feed(
        _feed(
            _item(
                auto_open=True,
                url="https://t.me/remna_shop",
                slides=[
                    {
                        "image": "2026-10/1.webp",
                        "text": {"en": "a"},
                        "url": "https://github.com/remnashop/remnashop/releases",
                    }
                ],
            )
        )
    )
    assert item.auto_open is True
    assert item.slides[0].image == "2026-10/1.webp"


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"items": {}}', b"{}"])
def test_malformed_feed_raises(body: bytes) -> None:
    with pytest.raises(FeedError):
        parse_feed(body)


def test_empty_items_is_a_valid_empty_feed() -> None:
    assert parse_feed(b'{"items": []}') == []


def test_url_label_is_localized_and_capped() -> None:
    items = parse_feed(
        _feed(
            _item(id="ok", url_label={"ru": "Поддержать", "en": "Support"}),
            _item(id="long", url_label={"en": "x" * 41}),
            _item(
                id="slide",
                auto_open=True,
                slides=[{"text": {"en": "a"}, "url_label": {"en": "Go"}}],
            ),
        )
    )
    assert [i.id for i in items] == ["ok", "slide"]
    assert items[0].url_label == {"ru": "Поддержать", "en": "Support"}
    assert items[1].slides[0].url_label == {"en": "Go"}
