import { apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";

export interface BotSettings {
  is_configured: boolean;
  drop_pending_updates: boolean;
}

export interface UpdateBotSettingsPayload {
  token?: string;
  secret_token?: string;
  drop_pending_updates?: boolean;
}

export function getBotSettings(signal?: AbortSignal): Promise<BotSettings> {
  return apiGet<BotSettings>("/settings/bot", signal);
}

export interface BotStatus {
  is_configured: boolean;
  is_running: boolean;
  webhook_url: string | null;
  pending_update_count: number;
  error: string | null;
}

export function getBotStatus(signal?: AbortSignal): Promise<BotStatus> {
  return apiGet<BotStatus>("/settings/bot/status", signal);
}

export function getBotLogs(signal?: AbortSignal): Promise<string[]> {
  return apiGet<{ lines: string[] }>("/settings/bot/logs", signal).then((response) => response.lines);
}

export function updateBotSettings(payload: UpdateBotSettingsPayload): Promise<BotSettings> {
  return apiPatch<BotSettings, UpdateBotSettingsPayload>("/settings/bot", payload);
}

export function restartBot(): Promise<null> {
  return apiPost<null, Record<string, never>>("/settings/bot/actions/restart", {});
}

export interface BotCommandItem {
  command: string;
  enabled: boolean;
}

export interface UpdateBotCommandsResult {
  commands: BotCommandItem[];
  telegram_sync_failed: boolean;
}

export function getBotCommands(
  signal?: AbortSignal,
  defaultOrder = false,
): Promise<BotCommandItem[]> {
  return apiGet<{ commands: BotCommandItem[] }>(
    `/settings/bot/commands${defaultOrder ? "?default_order=true" : ""}`,
    signal,
  ).then((response) => response.commands);
}

export function updateBotCommands(commands: BotCommandItem[]): Promise<UpdateBotCommandsResult> {
  return apiPut<UpdateBotCommandsResult, { commands: BotCommandItem[] }>(
    "/settings/bot/commands",
    { commands },
  );
}

export interface OAuthSettings {
  is_github_configured: boolean;
  is_github_enabled: boolean;
  is_telegram_configured: boolean;
  is_telegram_enabled: boolean;
  is_oidc_configured: boolean;
  is_oidc_enabled: boolean;
  oidc_display_name: string | null;
  is_password_login_enabled: boolean;
  is_passkey_configured: boolean;
  is_passkey_enabled: boolean;
  passkey_rp_id: string | null;
  passkey_origin: string | null;
}

export interface UpdateOAuthSettingsPayload {
  github_client_id?: string;
  github_client_secret?: string;
  github_enabled?: boolean;
  telegram_client_id?: string;
  telegram_client_secret?: string;
  telegram_enabled?: boolean;
  oidc_issuer_url?: string;
  oidc_client_id?: string;
  oidc_client_secret?: string;
  oidc_display_name?: string;
  oidc_enabled?: boolean;
  password_login_enabled?: boolean;
  passkey_enabled?: boolean;
  passkey_rp_id?: string;
  passkey_origin?: string;
}

export function getOAuthSettings(signal?: AbortSignal): Promise<OAuthSettings> {
  return apiGet<OAuthSettings>("/settings/oauth", signal);
}

export function updateOAuthSettings(payload: UpdateOAuthSettingsPayload): Promise<OAuthSettings> {
  return apiPatch<OAuthSettings, UpdateOAuthSettingsPayload>("/settings/oauth", payload);
}

export interface ShopSettings {
  max_active_subscriptions: number | null;
  device_single_reset_enabled: boolean;
  device_single_reset_cooldown_hours: number;
  device_all_reset_enabled: boolean;
  device_all_reset_cooldown_hours: number;
  link_reset_enabled: boolean;
  link_reset_cooldown_hours: number;
}

export type UpdateShopSettingsPayload = ShopSettings;

export function getShopSettings(signal?: AbortSignal): Promise<ShopSettings> {
  return apiGet<ShopSettings>("/settings/shop", signal);
}

export function updateShopSettings(payload: UpdateShopSettingsPayload): Promise<ShopSettings> {
  return apiPatch<ShopSettings, UpdateShopSettingsPayload>("/settings/shop", payload);
}
