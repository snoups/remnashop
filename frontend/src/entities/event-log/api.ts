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
  search?: string;
  dateFrom?: string;
  dateTo?: string;
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
  if (filters.search) params.set("search", filters.search);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
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
  return apiPost<void, Record<string, never>>("/event-log/notifications/read", {});
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
