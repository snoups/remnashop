import { EMPTY_AUDIENCE } from "@entities/broadcasts/api";
import type { Broadcast, BroadcastButtonKind, BroadcastInput } from "@entities/broadcasts/api";

export type EditorForm = BroadcastInput;

// the API returns a datetime; the date pickers work in "YYYY-MM-DD"
const toDate = (value: string | null) => (value ? value.slice(0, 10) : null);

export function toForm(b: Broadcast | null, defaultLocale: string): EditorForm {
  if (!b) {
    return {
      title: null,
      category: "SERVICE",
      audience: EMPTY_AUDIENCE,
      default_locale: defaultLocale,
      contents: { [defaultLocale]: { text: "", button_labels: [] } },
      buttons: [],
      promocode_id: null,
      post_to_channel: false,
    };
  }
  return {
    title: b.title,
    category: b.category,
    audience: {
      ...b.audience,
      registered_from: toDate(b.audience.registered_from),
      registered_to: toDate(b.audience.registered_to),
    },
    default_locale: b.default_locale,
    contents: b.contents,
    buttons: b.buttons,
    promocode_id: b.promocode_id,
    post_to_channel: b.post_to_channel,
  };
}

export function addLocale(f: EditorForm, locale: string): EditorForm {
  const labels = f.contents[f.default_locale]?.button_labels ?? [];
  return { ...f, contents: { ...f.contents, [locale]: { text: "", button_labels: [...labels] } } };
}

export function removeLocale(f: EditorForm, locale: string): EditorForm {
  if (locale === f.default_locale) return f;
  const { [locale]: _removed, ...contents } = f.contents;
  return { ...f, contents };
}

export function addButton(f: EditorForm, kind: BroadcastButtonKind): EditorForm {
  const contents = Object.fromEntries(
    Object.entries(f.contents).map(([locale, c]) => [locale, { ...c, button_labels: [...c.button_labels, ""] }]),
  );
  return { ...f, buttons: [...f.buttons, { kind, url: kind === "URL" ? "" : null }], contents };
}

export function removeButton(f: EditorForm, index: number): EditorForm {
  const contents = Object.fromEntries(
    Object.entries(f.contents).map(([locale, c]) => [
      locale,
      { ...c, button_labels: c.button_labels.filter((_, i) => i !== index) },
    ]),
  );
  return { ...f, buttons: f.buttons.filter((_, i) => i !== index), contents };
}

export function setText(f: EditorForm, locale: string, text: string): EditorForm {
  return { ...f, contents: { ...f.contents, [locale]: { ...f.contents[locale], text } } };
}

export function setButtonLabel(f: EditorForm, locale: string, index: number, label: string): EditorForm {
  const content = f.contents[locale];
  const button_labels = content.button_labels.map((l, i) => (i === index ? label : l));
  return { ...f, contents: { ...f.contents, [locale]: { ...content, button_labels } } };
}

export function setButtonUrl(f: EditorForm, index: number, url: string): EditorForm {
  return { ...f, buttons: f.buttons.map((b, i) => (i === index ? { ...b, url } : b)) };
}

// sorted keys: a saved form and a reloaded one may list the same keys in another order
function stableStringify(value: unknown): string {
  return JSON.stringify(value, (_key, v: unknown) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(Object.entries(v).sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0)))
      : v,
  );
}

export function isDirty(a: EditorForm, b: EditorForm): boolean {
  return stableStringify(a) !== stableStringify(b);
}
