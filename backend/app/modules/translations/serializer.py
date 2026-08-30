from collections import defaultdict

from app.modules.translations.dto import TranslationEntryDto


def serialize_to_fluent(entries: list[TranslationEntryDto]) -> str:
    by_message: dict[str, list[TranslationEntryDto]] = defaultdict(list)
    for entry in entries:
        by_message[entry.message_id].append(entry)

    lines: list[str] = []
    for message_id in sorted(by_message):
        group = sorted(by_message[message_id], key=lambda entry: entry.attribute_id)
        own_value = next((entry.value for entry in group if entry.attribute_id == ""), None)
        lines.append(f"{message_id} = {own_value}" if own_value is not None else f"{message_id} =")
        for entry in group:
            if entry.attribute_id:
                lines.append(f"    .{entry.attribute_id} = {entry.value}")

    return "\n".join(lines) + "\n"


def contains_placeable(text: str) -> bool:
    # Lazy import -- fluent.syntax ships with fluent_compiler, which lives
    # under the `telegram` extra.
    from fluent.syntax import FluentParser  # noqa: PLC0415
    from fluent.syntax.ast import Message, Pattern, Placeable  # noqa: PLC0415

    patterns: list[Pattern] = []
    for entry in FluentParser().parse(text).body:
        if not isinstance(entry, Message):
            continue
        if entry.value is not None:
            patterns.append(entry.value)
        patterns.extend(attribute.value for attribute in entry.attributes)

    return any(
        isinstance(element, Placeable) for pattern in patterns for element in pattern.elements
    )
