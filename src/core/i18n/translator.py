from typing import Any

from fluentogram import TranslatorRunner


def get_translated_kwargs(i18n: TranslatorRunner, kwargs: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for k, v in kwargs.items():
        # case ("key", {"value": 5})
        if (
            isinstance(v, tuple)
            and len(v) == 2
            and isinstance(v[0], str)
            and isinstance(v[1], dict)
        ):
            key, sub_kwargs = v
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = i18n.get(key, **processed_sub_kwargs)

        # case {"key": "some.key", "value": 5}
        elif isinstance(v, dict) and "key" in v:
            key = v["key"]
            sub_kwargs = {sub_k: sub_v for sub_k, sub_v in v.items() if sub_k != "key"}
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = i18n.get(key, **processed_sub_kwargs)

        # case ["key", {"value": 5}]
        elif (
            isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], dict)
        ):
            key, sub_kwargs = v
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = i18n.get(key, **processed_sub_kwargs)

        # case [("day", {"value": 6}), ("hour", {"value": 23})]
        elif isinstance(v, list) and all(
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], dict)
            for item in v
        ):
            parts = [
                i18n.get(item_key, **get_translated_kwargs(i18n, item_kwargs))
                for item_key, item_kwargs in v
            ]
            result[k] = " ".join(parts)

        # generic list
        elif isinstance(v, list):
            result[k] = [
                get_translated_kwargs(i18n, {"_": item})["_"]
                if isinstance(item, (tuple, dict, list))
                else item
                for item in v
            ]

        # fallback
        else:
            result[k] = v

    return result
