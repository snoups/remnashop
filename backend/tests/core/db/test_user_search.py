from app.core.db.user_search import user_search_filter


def test_non_ascii_digits_are_searched_as_text() -> None:
    user_search_filter("²")
    user_search_filter("٣")
