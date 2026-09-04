import { apiDelete, apiGet, apiPost, apiPut } from "@shared/api/http";

export interface ActiveLocalesResult {
  active: string[];
  available: string[];
}

export interface TranslationEntry {
  locale: string;
  message_id: string;
  attribute_id: string;
  value: string;
  default_value: string;
}

export function listActiveLocales(signal?: AbortSignal): Promise<ActiveLocalesResult> {
  return apiGet<ActiveLocalesResult>("/settings/locales", signal);
}

export function addLocale(locale: string): Promise<ActiveLocalesResult> {
  return apiPost<ActiveLocalesResult, { locale: string }>("/settings/locales", { locale });
}

export function removeLocale(locale: string): Promise<ActiveLocalesResult> {
  return apiDelete<ActiveLocalesResult>(`/settings/locales/${locale}`);
}

export function listTranslations(signal?: AbortSignal): Promise<TranslationEntry[]> {
  return apiGet<TranslationEntry[]>("/translations", signal);
}

export function updateTranslation(
  locale: string,
  messageId: string,
  attributeId: string,
  value: string,
): Promise<TranslationEntry> {
  const query = attributeId ? `?attribute_id=${encodeURIComponent(attributeId)}` : "";
  return apiPut<TranslationEntry, { value: string }>(
    `/translations/${locale}/${messageId}${query}`,
    { value },
  );
}

export function resetTranslation(
  locale: string,
  messageId: string,
  attributeId: string,
): Promise<TranslationEntry> {
  const query = attributeId ? `?attribute_id=${encodeURIComponent(attributeId)}` : "";
  return apiPost<TranslationEntry, Record<string, never>>(
    `/translations/${locale}/${messageId}/reset${query}`,
    {},
  );
}
