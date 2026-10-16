import { EMPTY_AUDIENCE } from "@entities/broadcasts/api";
import type { Broadcast, BroadcastButtonKind, BroadcastDelivery, BroadcastInput } from "@entities/broadcasts/api";

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
      delivery: "TELEGRAM",
      email_fallback: false,
      contents: { [defaultLocale]: { text: "", button_labels: [] } },
      email_contents: {},
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
    delivery: b.delivery,
    email_fallback: b.email_fallback,
    contents: b.contents,
    email_contents: b.email_contents,
    buttons: b.buttons,
    promocode_id: b.promocode_id,
    post_to_channel: b.post_to_channel,
  };
}

export const sendsTelegram = (f: EditorForm) => f.delivery !== "EMAIL";
export const sendsEmail = (f: EditorForm) => f.delivery !== "TELEGRAM" || f.email_fallback;

// mirrors the backend: the fallback only exists for Telegram-only delivery, the channel post never for email-only
export function setDelivery(f: EditorForm, delivery: BroadcastDelivery): EditorForm {
  return {
    ...f,
    delivery,
    email_fallback: delivery === "TELEGRAM" && f.email_fallback,
    post_to_channel: delivery !== "EMAIL" && f.post_to_channel,
  };
}

export function setEmailFallback(f: EditorForm, on: boolean): EditorForm {
  return { ...f, email_fallback: on };
}

export function addLocale(f: EditorForm, locale: string): EditorForm {
  const labels = f.contents[f.default_locale]?.button_labels ?? [];
  const next = { ...f, contents: { ...f.contents, [locale]: { text: "", button_labels: [...labels] } } };
  return sendsEmail(f) ? { ...next, email_contents: { ...f.email_contents, [locale]: { subject: "", html: "" } } } : next;
}

export function removeLocale(f: EditorForm, locale: string): EditorForm {
  if (locale === f.default_locale) return f;
  const { [locale]: _removed, ...contents } = f.contents;
  const { [locale]: _removedEmail, ...email_contents } = f.email_contents;
  return { ...f, contents, email_contents };
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

// a locale added before email delivery was switched on has no email entry yet
const emailContent = (f: EditorForm, locale: string) => f.email_contents[locale] ?? { subject: "", html: "" };

export function setEmailSubject(f: EditorForm, locale: string, subject: string): EditorForm {
  return { ...f, email_contents: { ...f.email_contents, [locale]: { ...emailContent(f, locale), subject } } };
}

export function setEmailHtml(f: EditorForm, locale: string, html: string): EditorForm {
  return { ...f, email_contents: { ...f.email_contents, [locale]: { ...emailContent(f, locale), html } } };
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
