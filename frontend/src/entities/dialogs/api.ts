import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export type DialogWindowKind = "seed" | "custom";
export type DialogFlow =
  | "menu"
  | "purchase"
  | "renewal"
  | "change"
  | "subscription"
  | "promocode"
  | "custom";
export type ButtonLinkType = "action" | "navigate" | "url" | "web_app";
export type ButtonStyleKind = "primary" | "success" | "danger";

export interface DialogButtonItem {
  /** Null for a button added in the editor and not saved yet. */
  id: number | null;
  row: number;
  column: number;
  text_key: string;
  style: ButtonStyleKind | null;
  visibility_condition: string | null;
  link_type: ButtonLinkType;
  action_key: string | null;
  target_window_key: string | null;
  url_value: string | null;
  is_hidden: boolean;
  is_system: boolean;
}

export interface DialogWindow {
  key: string;
  kind: DialogWindowKind;
  flow: DialogFlow;
  banner_name: string | null;
  name: string | null;
  is_enabled: boolean;
  position: number;
  text_keys: string[];
  buttons: DialogButtonItem[];
}

export interface DialogCatalog {
  action_keys: string[];
  condition_keys: string[];
  variable_keys: string[];
  text_variable_keys: string[];
  /** A window's own variables, on top of text_variable_keys. */
  window_text_variable_keys: Record<string, string[]>;
  /** variable -> its picker group: "user", "subscription", ... */
  variable_categories: Record<string, string>;
  seed_window_keys: string[];
  navigable_window_keys: string[];
  custom_window_limit: number;
}

export interface DialogTextEntry {
  locale: string;
  message_id: string;
  value: string;
  default_value: string;
}

export interface DialogButtonInput {
  row: number;
  column: number;
  text_key: string;
  link_type: ButtonLinkType;
  style?: ButtonStyleKind | null;
  visibility_condition?: string | null;
  action_key?: string | null;
  target_window_key?: string | null;
  url_value?: string | null;
  is_hidden?: boolean;
}

export function toButtonInput(button: DialogButtonItem): DialogButtonInput {
  return {
    row: button.row,
    column: button.column,
    text_key: button.text_key,
    link_type: button.link_type,
    style: button.style,
    visibility_condition: button.visibility_condition,
    action_key: button.action_key,
    target_window_key: button.target_window_key,
    url_value: button.url_value,
    is_hidden: button.is_hidden,
  };
}

/** Identifies a button across edits: its row/column change under drag and drop,
 * and its text key is only unique by convention. */
export function buttonKey(button: DialogButtonItem): string {
  return button.id === null ? `new:${button.text_key}` : `id:${button.id}`;
}

/** Mirrors modules/dialogs/catalog.py: a button's icon is a translation of its
 * own, so it can differ per locale. Exactly one of the two is filled: a plain
 * glyph or a premium custom emoji id. */
export function iconTextKey(textKey: string): string {
  return `${textKey}-icon`;
}

export function iconIdTextKey(textKey: string): string {
  return `${textKey}-icon-id`;
}

export function windowTextKeys(window: DialogWindow): string[] {
  return [...window.text_keys, ...window.buttons.map((button) => button.text_key)];
}

/** Mirrors core/constants.py. A window stores a banner name: unset means no
 * banner, SHARED_BANNER_NAME means the one shared by every window, and anything
 * else is that window's own. */
export const SHARED_BANNER_NAME = "default";
const WINDOW_BANNER_PREFIX = "win.";

export type BannerMode = "none" | "shared" | "own";

export function bannerMode(bannerName: string | null): BannerMode {
  if (bannerName === null) return "none";
  return bannerName === SHARED_BANNER_NAME ? "shared" : "own";
}

export function windowBannerName(windowKey: string): string {
  return `${WINDOW_BANNER_PREFIX}${windowKey}`;
}

/** The name a window's banner takes in each mode; null means "no banner". */
export function bannerNameForMode(mode: BannerMode, windowKey: string): string | null {
  if (mode === "none") return null;
  return mode === "shared" ? SHARED_BANNER_NAME : windowBannerName(windowKey);
}

const URL_VARIABLE_RE = /\$\{([a-z0-9_.]+)\}/g;
/** Mirrors the backend's own rule (modules/dialogs/catalog.py): Telegram rejects
 * a whole keyboard over one bad button URL. */
const URL_SCHEMES = ["https://", "http://", "tg://"];
/** Telegram opens a Mini App only over HTTPS. */
const WEB_APP_SCHEMES = ["https://"];

export function isLinkButton(linkType: ButtonLinkType): boolean {
  return linkType === "url" || linkType === "web_app";
}

export function urlSchemesFor(linkType: ButtonLinkType): string[] {
  return linkType === "web_app" ? WEB_APP_SCHEMES : URL_SCHEMES;
}

export type UrlProblem =
  | { kind: "scheme" }
  | { kind: "malformed" }
  | { kind: "variable"; name: string };

export function urlProblem(
  value: string,
  variableKeys: string[],
  schemes: string[] = URL_SCHEMES,
): UrlProblem | null {
  if (/\s/.test(value) || schemes.includes(value)) return { kind: "malformed" };
  for (const match of value.matchAll(URL_VARIABLE_RE)) {
    if (!variableKeys.includes(match[1])) return { kind: "variable", name: match[1] };
  }
  const literal = value.replace(URL_VARIABLE_RE, "");
  if (literal && !schemes.some((scheme) => literal.startsWith(scheme))) {
    return { kind: "scheme" };
  }
  return null;
}

/** Mirrors modules/dialogs/validation.py: Telegram refuses the whole keyboard
 * or message past these. */
export const MAX_BUTTONS_PER_ROW = 8;
export const MAX_BUTTONS = 100;
export const MAX_TEXT_LENGTH = 4096;
export const MAX_CAPTION_LENGTH = 1024;

/** `[glyph](emoji:id)`: premium emoji markup inside dialog text. */
export const PREMIUM_EMOJI_RE = /\[([^[\]]{1,16})\]\(emoji:(\d{1,24})\)/g;

export interface VariableOption {
  name: string;
  category: string;
}

/** Catalog variables for a picker; a window's own ones group as "window". */
export function variableOptions(
  catalog: DialogCatalog | null,
  keys: string[],
  windowKeys: string[] = [],
): VariableOption[] {
  return [
    ...keys.map((name) => ({ name, category: catalog?.variable_categories[name] ?? "other" })),
    ...windowKeys.map((name) => ({ name, category: "window" })),
  ];
}

export type TextPart = string | { glyph: string; customEmojiId: string };

/** Plain runs and premium emoji, in order, for drawing the emoji themselves. */
export function splitPremiumEmoji(value: string): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of value.matchAll(PREMIUM_EMOJI_RE)) {
    if (match.index > last) parts.push(value.slice(last, match.index));
    parts.push({ glyph: match[1], customEmojiId: match[2] });
    last = match.index + match[0].length;
  }
  if (last < value.length) parts.push(value.slice(last));
  return parts;
}

/** What Telegram counts: UTF-16 units, with premium emoji markup as its glyph. */
export function sentTextLength(value: string): number {
  return value.replace(PREMIUM_EMOJI_RE, "$1").length;
}

/** A window text is Telegram HTML: tags are not counted, entities count as the character. */
export function sentHtmlLength(value: string): number {
  return sentTextLength(
    value
      .replace(/<[^>]*>/g, "")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&amp;/g, "&"),
  );
}

export function buttonLimitProblem(
  buttons: DialogButtonItem[],
): { kind: "row" | "total"; max: number } | null {
  const shown = buttons.filter((button) => !button.is_hidden);
  if (shown.length > MAX_BUTTONS) return { kind: "total", max: MAX_BUTTONS };
  const perRow = new Map<number, number>();
  for (const button of shown) perRow.set(button.row, (perRow.get(button.row) ?? 0) + 1);
  if ([...perRow.values()].some((count) => count > MAX_BUTTONS_PER_ROW)) {
    return { kind: "row", max: MAX_BUTTONS_PER_ROW };
  }
  return null;
}

export function invalidUrlButton(
  buttons: DialogButtonItem[],
  variableKeys: string[],
): DialogButtonItem | null {
  return (
    buttons.find(
      (button) =>
        isLinkButton(button.link_type) &&
        (!button.url_value ||
          urlProblem(button.url_value, variableKeys, urlSchemesFor(button.link_type)) !== null),
    ) ?? null
  );
}

export function splitTextKey(key: string): { messageId: string; attributeId: string } {
  const dotIndex = key.lastIndexOf(".");
  if (dotIndex === -1) return { messageId: key, attributeId: "" };
  return { messageId: key.slice(0, dotIndex), attributeId: key.slice(dotIndex + 1) };
}

export function listWindows(signal?: AbortSignal): Promise<DialogWindow[]> {
  return apiGet<ListResponse<DialogWindow>>("/dialogs/windows", signal).then((response) => response.items);
}

export function getCatalog(signal?: AbortSignal): Promise<DialogCatalog> {
  return apiGet<DialogCatalog>("/dialogs/catalog", signal);
}

export function updateWindow(
  key: string,
  data: { banner_name?: string | null; is_enabled?: boolean; name?: string },
): Promise<DialogWindow> {
  return apiPatch<DialogWindow, typeof data>(`/dialogs/windows/${encodeURIComponent(key)}`, data);
}

export function replaceButtons(key: string, buttons: DialogButtonInput[]): Promise<DialogWindow> {
  return apiPut<DialogWindow, { buttons: DialogButtonInput[] }>(
    `/dialogs/windows/${encodeURIComponent(key)}/buttons`,
    { buttons },
  );
}

/** The banner is deliberately not sent: the backend then starts the window on
 * the shared one, which is what every window gets until an admin says otherwise. */
export function createCustomWindow(name: string): Promise<DialogWindow> {
  return apiPost<DialogWindow, { name: string }>("/dialogs/windows", {
    name,
  });
}

export function deleteCustomWindow(key: string): Promise<null> {
  return apiDelete<null>(`/dialogs/windows/${encodeURIComponent(key)}`);
}

export function resetWindow(key: string): Promise<DialogWindow> {
  return apiPost<DialogWindow, Record<string, never>>(
    `/dialogs/windows/${encodeURIComponent(key)}/actions/reset`,
    {},
  );
}

export interface DialogExportPayload {
  version: number;
  windows: unknown[];
  texts: unknown[];
}

export function exportDialogs(): Promise<DialogExportPayload> {
  return apiGet<DialogExportPayload>("/dialogs/export");
}

export function importDialogs(payload: DialogExportPayload): Promise<null> {
  return apiPost<null, DialogExportPayload>("/dialogs/actions/import", payload);
}

export function resetAll(): Promise<DialogWindow[]> {
  return apiPost<ListResponse<DialogWindow>, Record<string, never>>("/dialogs/actions/reset-all", {}).then(
    (response) => response.items,
  );
}

export function updateDialogText(
  locale: string,
  messageId: string,
  attributeId: string,
  value: string,
): Promise<DialogTextEntry> {
  const query = attributeId ? `?attribute_id=${encodeURIComponent(attributeId)}` : "";
  return apiPut<DialogTextEntry, { value: string }>(
    `/dialogs/text/${locale}/${encodeURIComponent(messageId)}${query}`,
    { value },
  );
}
