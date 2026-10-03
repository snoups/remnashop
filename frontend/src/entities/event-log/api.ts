import { apiGet, apiPost, apiPut } from "@shared/api/http";

export const DEFAULT_PAGE_SIZE = 50;

export interface EventLogEntry {
  id: number;
  category: string;
  event_type: string;
  occurred_at: string;
  actor_id: number | null;
  actor_login: string | null;
  actor_name: string | null;
  ip_address: string | null;
  payload: Record<string, unknown>;
}

// `location.state` for /dashboard/event-log: opens that entry's detail dialog on arrival
export interface EventLogLocationState {
  entry: EventLogEntry;
}

export interface EventLogPage {
  items: EventLogEntry[];
  total: number;
}

export interface EventLogFilters {
  category?: string;
  actorId?: number;
  /** the account the event was about */
  targetId?: number;
  eventType?: string;
  search?: string;
  occurredFrom?: string;
  occurredTo?: string;
  page?: number;
  pageSize?: number;
}

export function listEventLog(
  filters: EventLogFilters = {},
  signal?: AbortSignal,
): Promise<EventLogPage> {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.actorId !== undefined) params.set("actor_id", String(filters.actorId));
  if (filters.targetId !== undefined) params.set("target_id", String(filters.targetId));
  if (filters.eventType) params.set("event_type", filters.eventType);
  if (filters.search) params.set("search", filters.search);
  if (filters.occurredFrom) params.set("occurred_from", filters.occurredFrom);
  if (filters.occurredTo) params.set("occurred_to", filters.occurredTo);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<EventLogPage>(`/event-log?${params.toString()}`, signal);
}

export interface Notifications {
  items: EventLogEntry[];
  unread_count: number;
}

export function getNotifications(signal?: AbortSignal): Promise<Notifications> {
  return apiGet<Notifications>("/event-log/notifications", signal);
}

export function markNotificationsRead(): Promise<void> {
  return apiPost<void, Record<string, never>>("/event-log/notifications/actions/mark-read", {});
}

export function clearNotifications(): Promise<void> {
  return apiPost<void, Record<string, never>>("/event-log/notifications/actions/clear", {});
}

export interface NotificationGroups {
  groups: string[];
  available: string[];
}

export function getNotificationGroups(signal?: AbortSignal): Promise<NotificationGroups> {
  return apiGet<NotificationGroups>("/event-log/notifications/groups", signal);
}

export function updateNotificationGroups(groups: string[]): Promise<NotificationGroups> {
  return apiPut<NotificationGroups, { groups: string[] }>("/event-log/notifications/groups", { groups });
}
