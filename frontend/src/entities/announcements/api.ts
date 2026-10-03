import { apiGet, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export interface AnnouncementSlide {
  image_url: string | null;
  text: Record<string, string>;
  url: string | null;
  url_label: Record<string, string>;
}

export interface Announcement {
  id: string;
  icon: string;
  severity: "info" | "critical";
  title: Record<string, string>;
  text: Record<string, string>;
  url: string | null;
  url_label: Record<string, string>;
  notify_at: string;
  auto_open: boolean;
  slides: AnnouncementSlide[];
  seen: boolean;
}

export function listAnnouncements(signal?: AbortSignal): Promise<ListResponse<Announcement>> {
  return apiGet<ListResponse<Announcement>>("/announcements", signal);
}

export function markAnnouncementsSeen(ids: string[]): Promise<void> {
  return apiPost<void, { ids: string[] }>("/announcements/actions/mark-seen", { ids });
}

export function dismissAnnouncements(ids: string[]): Promise<void> {
  return apiPost<void, { ids: string[] }>("/announcements/actions/dismiss", { ids });
}

/** The maintainer writes each text per locale; fall back to English, then to whatever exists. */
export function localized(map: Record<string, string>, language: string): string {
  return map[language] ?? map.en ?? Object.values(map)[0] ?? "";
}
