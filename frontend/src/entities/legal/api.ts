import { apiDelete, apiGet, apiPatch, apiPut } from "@shared/api/http";

export type LegalKind = "OFFER" | "USER_AGREEMENT" | "PRIVACY_POLICY";
export type LegalChannel = "BOT" | "CABINET";

export interface LegalText {
  locale: string;
  channel: LegalChannel | null;
  title: string;
  body: string;
  revision_id: number;
  created_at: string;
  requires_reacceptance: boolean;
  last_reacceptance_at: string | null;
}

export interface LegalDocument {
  kind: LegalKind;
  show_in_bot: boolean;
  show_in_cabinet: boolean;
  texts: LegalText[];
}

export interface LegalDocumentsResponse {
  items: LegalDocument[];
  total: number;
  offer_missing_in: LegalChannel[];
  locales: string[];
}

export interface LegalAcceptance {
  id: number;
  kind: LegalKind;
  locale: string;
  channel: LegalChannel;
  trigger: "SIGN_UP" | "PAYMENT";
  transaction_id: number | null;
  accepted_at: string;
  revision_id: number;
  title: string;
}

export const LEGAL_KINDS: LegalKind[] = ["OFFER", "USER_AGREEMENT", "PRIVACY_POLICY"];

export function listLegalDocuments(signal?: AbortSignal): Promise<LegalDocumentsResponse> {
  return apiGet<LegalDocumentsResponse>("/legal-documents", signal);
}

export function updateLegalDocument(
  kind: LegalKind,
  payload: { show_in_bot?: boolean; show_in_cabinet?: boolean },
): Promise<Omit<LegalDocument, "texts">> {
  return apiPatch<Omit<LegalDocument, "texts">, typeof payload>(`/legal-documents/${kind}`, payload);
}

function textPath(kind: LegalKind, locale: string, channel: LegalChannel | null): string {
  return `/legal-documents/${kind}/${locale}${channel ? `?channel=${channel}` : ""}`;
}

export function setLegalText(
  kind: LegalKind,
  locale: string,
  channel: LegalChannel | null,
  payload: { title: string; body: string; requires_reacceptance: boolean },
): Promise<LegalText> {
  return apiPut<LegalText, typeof payload>(textPath(kind, locale, channel), payload);
}

export function removeLegalText(kind: LegalKind, locale: string, channel: LegalChannel | null): Promise<null> {
  return apiDelete<null>(textPath(kind, locale, channel));
}

export function listUserLegalAcceptances(
  userId: number,
  signal?: AbortSignal,
): Promise<{ items: LegalAcceptance[]; total: number }> {
  return apiGet<{ items: LegalAcceptance[]; total: number }>(`/users/${userId}/legal-acceptances`, signal);
}
