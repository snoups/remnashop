import { Handshake, ReceiptText, ShieldCheck } from "lucide-react";

import type { LegalChannel, LegalDocument, LegalKind, LegalText } from "@entities/legal/api";

const MESSAGE_LIMIT = 32768;
// the "# " heading and blank line the message adds around the title and text
const MARKUP_LENGTH = [..."# \n\n"].length;
export const TEXT_LIMIT = MESSAGE_LIMIT - MARKUP_LENGTH;
export const TITLE_LIMIT = 160;
export const KIND_ICONS: Record<LegalKind, typeof ReceiptText> = {
  OFFER: ReceiptText,
  USER_AGREEMENT: Handshake,
  PRIVACY_POLICY: ShieldCheck,
};
// the offer is accepted by paying, so only these can ask for it again
const REACCEPTABLE: readonly LegalKind[] = ["USER_AGREEMENT", "PRIVACY_POLICY"];

export interface TextDraft {
  title: string;
  body: string;
  reaccept: boolean;
}

export function draftKey(kind: LegalKind, locale: string, channel: LegalChannel | null): string {
  return `${kind}|${locale}|${channel ?? ""}`;
}

export function textLength(draft: Pick<TextDraft, "title" | "body">): number {
  return [...draft.title].length + [...draft.body].length;
}

/** What the editor shows for a key before any edit, and what the server holds for it. */
export function textSlot(document: LegalDocument, locale: string, channel: LegalChannel | null) {
  const own: LegalText | undefined = document.texts.find(
    (item) => item.locale === locale && item.channel === channel,
  );
  const common = document.texts.find((item) => item.locale === locale && item.channel === null);
  const template = channel === null ? document.templates.find((item) => item.locale === locale) : undefined;
  const hasOverride = channel !== null && !!own;
  // a channel without its own text shows the common one; an empty common text, the template
  const shown = (channel === null || hasOverride ? own : common) ?? template;
  return {
    own,
    hasOverride,
    template,
    baseline: { title: shown?.title ?? "", body: shown?.body ?? "" },
    // only an edit of a text customers already have can be put to them again
    canReaccept: REACCEPTABLE.includes(document.kind) && (channel === null ? !!own : hasOverride),
  };
}

export function isChanged(draft: TextDraft | undefined, baseline: { title: string; body: string }): boolean {
  return !!draft && (draft.title !== baseline.title || draft.body !== baseline.body);
}

export function isValid(draft: TextDraft): boolean {
  return !!draft.title.trim() && !!draft.body.trim() && textLength(draft) <= TEXT_LIMIT;
}
