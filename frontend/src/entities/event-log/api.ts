import { apiGet } from "@shared/api/http";

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

export interface EventLogPage {
  items: EventLogEntry[];
  total: number;
}

export interface EventLogFilters {
  category?: string;
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
  if (filters.search) params.set("search", filters.search);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<EventLogPage>(`/event-log?${params.toString()}`, signal);
}
