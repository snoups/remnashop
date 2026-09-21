import { apiDelete, apiGet, apiPost, apiPut } from "@shared/api/http";

export type DialogWindowKind = "seed" | "custom";
export type DialogFlow =
  | "menu"
  | "purchase"
  | "renewal"
  | "change"
  | "subscription"
  | "promocode"
  | "custom";
export type ButtonLinkType = "action" | "navigate" | "url";
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
}

export interface DialogWindow {
  key: string;
  kind: DialogWindowKind;
  flow: DialogFlow;
  banner_name: string | null;
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
 * own, so it can differ per locale. Exactly one of the two is ever filled -- a
 * plain glyph, or a premium custom emoji id. */
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
export const URL_SCHEMES = ["https://", "http://", "tg://"];

export type UrlProblem = { kind: "scheme" } | { kind: "variable"; name: string };

export function urlProblem(value: string, variableKeys: string[]): UrlProblem | null {
  for (const match of value.matchAll(URL_VARIABLE_RE)) {
    if (!variableKeys.includes(match[1])) return { kind: "variable", name: match[1] };
  }
  const literal = value.replace(URL_VARIABLE_RE, "");
  if (literal && !URL_SCHEMES.some((scheme) => literal.startsWith(scheme))) {
    return { kind: "scheme" };
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
        button.link_type === "url" &&
        (!button.url_value || urlProblem(button.url_value, variableKeys) !== null),
    ) ?? null
  );
}

export function splitTextKey(key: string): { messageId: string; attributeId: string } {
  const dotIndex = key.lastIndexOf(".");
  if (dotIndex === -1) return { messageId: key, attributeId: "" };
  return { messageId: key.slice(0, dotIndex), attributeId: key.slice(dotIndex + 1) };
}

export function listWindows(signal?: AbortSignal): Promise<DialogWindow[]> {
  return apiGet<DialogWindow[]>("/dialogs/windows", signal);
}

export function getWindow(key: string, signal?: AbortSignal): Promise<DialogWindow> {
  return apiGet<DialogWindow>(`/dialogs/windows/${encodeURIComponent(key)}`, signal);
}

export function getCatalog(signal?: AbortSignal): Promise<DialogCatalog> {
  return apiGet<DialogCatalog>("/dialogs/catalog", signal);
}

export function updateWindow(
  key: string,
  data: { banner_name?: string | null; is_enabled?: boolean },
): Promise<DialogWindow> {
  return apiPut<DialogWindow, typeof data>(`/dialogs/windows/${encodeURIComponent(key)}`, data);
}

export function replaceButtons(key: string, buttons: DialogButtonInput[]): Promise<DialogWindow> {
  return apiPut<DialogWindow, { buttons: DialogButtonInput[] }>(
    `/dialogs/windows/${encodeURIComponent(key)}/buttons`,
    { buttons },
  );
}

export function createCustomWindow(
  titleText: string,
  bannerName?: string | null,
): Promise<DialogWindow> {
  return apiPost<DialogWindow, { title_text: string; banner_name?: string | null }>(
    "/dialogs/windows",
    { title_text: titleText, banner_name: bannerName },
  );
}

export function deleteCustomWindow(key: string): Promise<null> {
  return apiDelete<null>(`/dialogs/windows/${encodeURIComponent(key)}`);
}

export function resetWindow(key: string): Promise<DialogWindow> {
  return apiPost<DialogWindow, Record<string, never>>(
    `/dialogs/windows/${encodeURIComponent(key)}/reset`,
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
  return apiPost<null, DialogExportPayload>("/dialogs/import", payload);
}

export function resetAll(): Promise<null> {
  return apiPost<null, Record<string, never>>("/dialogs/reset", {});
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
