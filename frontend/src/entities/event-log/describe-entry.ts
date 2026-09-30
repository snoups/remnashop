import type { TFunction } from "i18next";

import type { EventLogEntry } from "@entities/event-log/api";

// Matches `ActorTargetEvent.target` (backend/app/core/events.py) -- `build_payload`
// derives payload keys from that dataclass's field names, so this has to stay in sync by hand.
export const PAYLOAD_TARGET_KEY = "target";

export function getTargetLogin(entry: EventLogEntry): string | undefined {
  return entry.payload &&
    typeof entry.payload === "object" &&
    PAYLOAD_TARGET_KEY in entry.payload
    ? (entry.payload as { [PAYLOAD_TARGET_KEY]?: { login?: string } })[PAYLOAD_TARGET_KEY]?.login
    : undefined;
}

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

// Requests from someone not signed in -- no actor exists, only the request's IP.
export const ANONYMOUS_EVENT_TYPES: ReadonlySet<string> = new Set([
  "LoginFailedEvent",
  "OAuthLoginFailedEvent",
  "PasskeyLoginFailedEvent",
  "BootstrapConflictEvent",
  "SessionTheftDetectedEvent",
]);

// The API-token actor has id 0 (api/dependencies/public.py), the system actor role SYSTEM.
export function isApiToken(user: UserSnapshot): boolean {
  return user.id === 0;
}

export function isSystemActor(user: UserSnapshot): boolean {
  return user.role === "SYSTEM";
}

export function getMissingInitiatorKey(entry: EventLogEntry): string {
  return ANONYMOUS_EVENT_TYPES.has(entry.event_type) ? "eventLog.detail.anonymous" : "eventLog.detail.system";
}

export function describeEntry(entry: EventLogEntry, t: TFunction): string {
  const initiator = getInitiator(entry);
  const actor = !initiator
    ? t(getMissingInitiatorKey(entry))
    : isSystemActor(initiator)
      ? t("eventLog.detail.system")
      : (initiator.login ?? initiator.name ?? "—");
  const target = getTargetLogin(entry);
  return target ? `${actor} → ${target}` : actor;
}
