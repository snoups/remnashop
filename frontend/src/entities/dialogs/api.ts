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
  row: number;
  column: number;
  text_key: string;
  icon_custom_emoji_id: string | null;
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
  icon_custom_emoji_id?: string | null;
  style?: ButtonStyleKind | null;
  visibility_condition?: string | null;
  action_key?: string | null;
  target_window_key?: string | null;
  url_value?: string | null;
  is_hidden?: boolean;
}

export function windowTextKeys(window: DialogWindow): string[] {
  return [...window.text_keys, ...window.buttons.map((button) => button.text_key)];
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
