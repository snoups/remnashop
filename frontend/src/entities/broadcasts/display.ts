import type { ParseKeys, TFunction } from "i18next";

import { RECALL_REPEAT_AFTER_MS, RECALL_WINDOW_MS } from "@entities/broadcasts/api";
import type {
  Broadcast,
  BroadcastAudience,
  BroadcastRecipientStatus,
  BroadcastStatus,
} from "@entities/broadcasts/api";
import { PREMIUM_EMOJI_RE } from "@entities/dialogs/api";
import type { BadgeTone } from "@shared/ui/Badge";

export const BROADCAST_STATUS_TONE: Record<BroadcastStatus, BadgeTone> = {
  DRAFT: "neutral",
  SCHEDULED: "violet",
  SENDING: "accent",
  COMPLETED: "success",
  CANCELED: "warning",
  FAILED: "error",
};

export const RECIPIENT_STATUS_TONE: Record<BroadcastRecipientStatus, BadgeTone> = {
  PENDING: "neutral",
  SENT: "success",
  FAILED: "error",
  BLOCKED: "warning",
  CANCELED: "warning",
  RECALLED: "violet",
};

const TITLE_MAX_LENGTH = 80;

function plainText(html: string): string {
  return html
    .replace(PREMIUM_EMOJI_RE, "$1")
    .replace(/<[^>]*>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

export function broadcastTitle(
  b: Pick<Broadcast, "title" | "contents" | "default_locale">,
  fallback: string,
): string {
  if (b.title) return b.title;
  const text = b.contents[b.default_locale]?.text ?? "";
  const line = plainText(text)
    .split("\n")
    .map((part) => part.trim())
    .find(Boolean);
  if (!line) return fallback;
  return line.length > TITLE_MAX_LENGTH ? `${line.slice(0, TITLE_MAX_LENGTH - 1)}…` : line;
}

export function broadcastMeta(b: Broadcast, t: TFunction): string {
  const parts = [Object.keys(b.contents).map((locale) => locale.toUpperCase()).join(", ")];
  if (b.media_type) parts.push(t(`broadcasts.media.${b.media_type}` as ParseKeys));
  if (b.promocode_id !== null) parts.push(t("broadcasts.meta.promocode"));
  if (b.post_to_channel) parts.push(t("broadcasts.meta.channel"));
  return parts.join(" · ");
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

export function audienceSummary(
  a: BroadcastAudience,
  t: TFunction,
  plans: { id: number; name: string }[],
): string {
  const parts: string[] = [];
  if (a.user_ids.length) parts.push(t("broadcasts.audience.users", { count: a.user_ids.length }));
  if (a.subscription.length) {
    parts.push(a.subscription.map((s) => t(`broadcasts.audience.subscription.${s}` as ParseKeys)).join(", "));
  }
  if (a.plan_ids.length) {
    const names = a.plan_ids.map((id) => plans.find((plan) => plan.id === id)?.name ?? `#${id}`);
    parts.push(t("broadcasts.audience.plans", { names: names.join(", ") }));
  }
  if (a.expires_within_days !== null) {
    parts.push(t("broadcasts.audience.expiresWithin", { days: a.expires_within_days }));
  }
  if (a.expired_within_days !== null) {
    parts.push(t("broadcasts.audience.expiredWithin", { days: a.expired_within_days }));
  }
  if (a.paid !== null) parts.push(t(a.paid ? "broadcasts.audience.paid" : "broadcasts.audience.notPaid"));
  if (a.locales.length) {
    parts.push(t("broadcasts.audience.locales", { locales: a.locales.map((l) => l.toUpperCase()).join(", ") }));
  }
  if (a.registered_from || a.registered_to) {
    parts.push(
      t("broadcasts.audience.registered", {
        from: a.registered_from ? formatDate(a.registered_from) : "…",
        to: a.registered_to ? formatDate(a.registered_to) : "…",
      }),
    );
  }
  if (a.ad_link_ids.length) parts.push(t("broadcasts.audience.adLinks", { count: a.ad_link_ids.length }));
  if (a.referred !== null) {
    parts.push(t(a.referred ? "broadcasts.audience.referred" : "broadcasts.audience.notReferred"));
  }
  return parts.length ? parts.join(", ") : t("broadcasts.audience.all");
}

export function processedCount(b: Broadcast): number {
  return b.sent_count + b.failed_count + b.blocked_count + b.recalled_count;
}

export function isEditable(b: Broadcast): boolean {
  return (b.status === "DRAFT" || b.status === "SCHEDULED") && !b.started_at;
}

export function isRecallRunning(b: Broadcast, now: number): boolean {
  return !!b.recall_requested_at && now - new Date(b.recall_requested_at).getTime() < RECALL_REPEAT_AFTER_MS;
}

export function canRecall(b: Broadcast, now: number): boolean {
  if (isRecallRunning(b, now)) return false;
  if (!b.started_at || now - new Date(b.started_at).getTime() >= RECALL_WINDOW_MS) return false;
  const left = b.recallable_count ?? b.sent_count;
  if (left === 0 && !b.has_channel_post) return false;
  return b.status === "SENDING" || b.status === "COMPLETED" || b.status === "CANCELED";
}
