import type { ParseKeys, TFunction } from "i18next";

import type { EventLogEntry } from "@entities/event-log/api";

// `ActorTargetEvent.target`: the outbox publisher's `_build_payload` takes
// payload keys from the dataclass fields, so keep this in sync by hand.
export const PAYLOAD_TARGET_KEY = "target";

export interface UserSnapshot {
  id?: number | null;
  login?: string | null;
  name?: string | null;
  role?: string | null;
  telegram_id?: number | null;
  username?: string | null;
  email?: string | null;
}

// Mirrors `_sanitize_user` (backend/app/core/outbox_event_publisher.py); rows
// written before telegram_id/username/email were added carry only id/login/name/role.
export function getUserSnapshot(entry: EventLogEntry, key: string): UserSnapshot | undefined {
  const value = entry.payload?.[key];
  return value && typeof value === "object" ? (value as UserSnapshot) : undefined;
}

export function getInitiator(entry: EventLogEntry): UserSnapshot | undefined {
  const snapshot = getUserSnapshot(entry, "actor") ?? getUserSnapshot(entry, "user");
  if (snapshot) return snapshot;
  if (entry.actor_id === null && !entry.actor_login && !entry.actor_name) return undefined;
  return { id: entry.actor_id, login: entry.actor_login, name: entry.actor_name };
}

// requests from someone not signed in: no actor, only the request's IP
export const ANONYMOUS_EVENT_TYPES: ReadonlySet<string> = new Set([
  "LoginFailedEvent",
  "OAuthLoginFailedEvent",
  "EmailCodeAttemptsExhaustedEvent",
  "PasskeyLoginFailedEvent",
  "BootstrapConflictEvent",
  "SessionTheftDetectedEvent",
  "PanelLoginFailedEvent",
  "PanelLoginSucceededEvent",
]);

// The API-token actor has id 0 (api/dependencies/public.py), the system actor role SYSTEM.
export function isApiToken(user: UserSnapshot): boolean {
  return user.id === 0;
}

export function isSystemActor(user: UserSnapshot): boolean {
  return user.role === "SYSTEM";
}

function getMissingInitiatorKey(entry: EventLogEntry): ParseKeys {
  return ANONYMOUS_EVENT_TYPES.has(entry.event_type) ? "eventLog.detail.anonymous" : "eventLog.detail.system";
}

/** Staff by login, a customer by name or "User #id"; an API token reads as its own name. */
function participantLabel(user: UserSnapshot, t: TFunction): string {
  if (isSystemActor(user)) return t("eventLog.detail.system");
  if (user.login) return user.login;
  if (user.name) return user.name;
  return user.id && user.id > 0 ? `${t("users.unnamed")} #${user.id}` : "—";
}

/** Who did it: a participant label, "System" or "Anonymous". */
export function initiatorLabel(entry: EventLogEntry, t: TFunction): string {
  const initiator = getInitiator(entry);
  return initiator ? participantLabel(initiator, t) : t(getMissingInitiatorKey(entry));
}

export function describeEntry(entry: EventLogEntry, t: TFunction): string {
  const actor = initiatorLabel(entry, t);
  const target = getUserSnapshot(entry, PAYLOAD_TARGET_KEY);
  return target ? `${actor} → ${participantLabel(target, t)}` : actor;
}

// payload field that picks `eventLog.eventVariants.<type>.<value>` over the plain title
const TITLE_VARIANT_FIELD = "action";
const TITLE_VARIANT_FIELD_OVERRIDES: Readonly<Record<string, string>> = {
  CabinetUserRegisteredEvent: "method",
};

const HOURS_PER_DAY = 24;

export function eventTitle(entry: EventLogEntry, t: TFunction): string {
  const title = t(`eventLog.events.${entry.event_type}` as ParseKeys);
  const hours = entry.payload?.hours;
  if (entry.event_type === "SubscriptionExpiredAgoEvent" && typeof hours === "number") {
    return t("eventLog.eventVariants.subscriptionExpiredDays", { count: Math.round(hours / HOURS_PER_DAY) });
  }
  const variant = entry.payload?.[TITLE_VARIANT_FIELD_OVERRIDES[entry.event_type] ?? TITLE_VARIANT_FIELD];
  if (typeof variant !== "string") return title;
  return t(`eventLog.eventVariants.${entry.event_type}.${variant}` as ParseKeys, { defaultValue: title });
}
