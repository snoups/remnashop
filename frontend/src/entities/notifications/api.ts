import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export interface NotificationChannels {
  channels: Record<string, string[]>;
  available_groups: string[];
  available_channels: string[];
  push_configured: boolean;
  telegram_available: boolean;
}

export interface PushSubscriptionItem {
  id: number;
  endpoint: string;
  user_agent: string | null;
  created_at: string;
  last_seen_at: string;
}

export interface PushSubscriptionBody {
  endpoint: string;
  keys: { p256dh: string; auth: string };
}

export interface NotificationSettings {
  is_push_configured: boolean;
  vapid_public_key: string | null;
  vapid_contact: string | null;
}

export function getNotificationChannels(signal?: AbortSignal): Promise<NotificationChannels> {
  return apiGet<NotificationChannels>("/notifications/channels", signal);
}

export function updateNotificationChannels(channels: Record<string, string[]>): Promise<NotificationChannels> {
  return apiPut<NotificationChannels, { channels: Record<string, string[]> }>("/notifications/channels", {
    channels,
  });
}

export function getPushPublicKey(): Promise<{ public_key: string | null }> {
  return apiGet<{ public_key: string | null }>("/notifications/push/public-key");
}

export function listPushSubscriptions(signal?: AbortSignal): Promise<ListResponse<PushSubscriptionItem>> {
  return apiGet<ListResponse<PushSubscriptionItem>>("/notifications/push-subscriptions", signal);
}

export function subscribePush(body: PushSubscriptionBody): Promise<PushSubscriptionItem> {
  return apiPost<PushSubscriptionItem, PushSubscriptionBody>("/notifications/push-subscriptions", body);
}

export function deletePushSubscription(id: number): Promise<void> {
  return apiDelete<void>(`/notifications/push-subscriptions/${id}`);
}

export function sendTestPush(): Promise<{ delivered: number }> {
  return apiPost<{ delivered: number }, Record<string, never>>("/notifications/push-subscriptions/actions/test", {});
}

export function getNotificationSettings(signal?: AbortSignal): Promise<NotificationSettings> {
  return apiGet<NotificationSettings>("/notifications/settings", signal);
}

export function updateNotificationSettings(body: { vapid_contact: string }): Promise<NotificationSettings> {
  return apiPatch<NotificationSettings, { vapid_contact: string }>("/notifications/settings", body);
}

export function generateVapidKeys(): Promise<NotificationSettings> {
  return apiPost<NotificationSettings, Record<string, never>>(
    "/notifications/settings/actions/generate-vapid-keys",
    {},
  );
}
