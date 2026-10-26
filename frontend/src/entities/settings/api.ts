import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";

export interface BotSettings {
  is_configured: boolean;
  is_proxy_configured: boolean;
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

export function setBotProxy(proxyUrl: string): Promise<BotSettings> {
  return apiPut<BotSettings, { proxy_url: string }>("/settings/bot/proxy", { proxy_url: proxyUrl });
}

export function removeBotProxy(): Promise<BotSettings> {
  return apiDelete<BotSettings>("/settings/bot/proxy");
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
  github_enabled: boolean;
  is_telegram_configured: boolean;
  telegram_enabled: boolean;
  is_google_configured: boolean;
  is_yandex_configured: boolean;
  is_oidc_configured: boolean;
  oidc_enabled: boolean;
  oidc_display_name: string | null;
  password_login_enabled: boolean;
  is_passkey_configured: boolean;
  passkey_enabled: boolean;
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
  google_client_id?: string;
  google_client_secret?: string;
  yandex_client_id?: string;
  yandex_client_secret?: string;
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

export type SmtpSecurity = "STARTTLS" | "TLS" | "NONE";

export interface EmailSettings {
  host: string | null;
  port: number;
  security: SmtpSecurity;
  username: string | null;
  is_password_set: boolean;
  from_address: string | null;
  from_name: string | null;
  is_configured: boolean;
  bulk_host: string | null;
  bulk_port: number;
  bulk_security: SmtpSecurity;
  bulk_username: string | null;
  is_bulk_password_set: boolean;
  bulk_from_address: string | null;
  bulk_from_name: string | null;
  bulk_rate_per_minute: number;
  is_bulk_configured: boolean;
}

export type UpdateEmailSettingsPayload = Partial<
  Omit<EmailSettings, "is_password_set" | "is_configured" | "is_bulk_password_set" | "is_bulk_configured"> & {
    password: string;
    bulk_password: string;
  }
>;

export function getEmailSettings(signal?: AbortSignal): Promise<EmailSettings> {
  return apiGet<EmailSettings>("/settings/email", signal);
}

export function updateEmailSettings(payload: UpdateEmailSettingsPayload): Promise<EmailSettings> {
  return apiPatch<EmailSettings, UpdateEmailSettingsPayload>("/settings/email", payload);
}

export function sendTestEmail(bulk = false): Promise<null> {
  return apiPost<null, { bulk: boolean }>("/settings/email/actions/test", { bulk });
}

export function resetBulkEmailSettings(): Promise<EmailSettings> {
  return apiPost<EmailSettings, Record<string, never>>("/settings/email/bulk/actions/reset", {});
}

export interface CabinetAuthSettings {
  telegram_enabled: boolean;
  telegram_oauth_enabled: boolean;
  google_enabled: boolean;
  yandex_enabled: boolean;
  email_enabled: boolean;
  restrict_email_domains: boolean;
  allowed_email_domains: string[];
}

export function getCabinetAuthSettings(signal?: AbortSignal): Promise<CabinetAuthSettings> {
  return apiGet<CabinetAuthSettings>("/settings/cabinet-auth", signal);
}

export function updateCabinetAuthSettings(
  payload: Partial<CabinetAuthSettings>,
): Promise<CabinetAuthSettings> {
  return apiPatch<CabinetAuthSettings, Partial<CabinetAuthSettings>>("/settings/cabinet-auth", payload);
}

export interface ShopSettings {
  max_active_subscriptions: number | null;
  device_single_reset_enabled: boolean;
  device_single_reset_cooldown_hours: number;
  device_all_reset_enabled: boolean;
  device_all_reset_cooldown_hours: number;
  link_reset_enabled: boolean;
  link_reset_cooldown_hours: number;
  referral_reset_enabled: boolean;
  referral_reset_cooldown_hours: number;
}

export type UpdateShopSettingsPayload = ShopSettings;

export function getShopSettings(signal?: AbortSignal): Promise<ShopSettings> {
  return apiGet<ShopSettings>("/settings/shop", signal);
}

export function updateShopSettings(payload: UpdateShopSettingsPayload): Promise<ShopSettings> {
  return apiPatch<ShopSettings, UpdateShopSettingsPayload>("/settings/shop", payload);
}

export type AccessMode = "PUBLIC" | "INVITED" | "RESTRICTED";

export interface AccessSettings {
  mode: AccessMode;
  registration_enabled: boolean;
  payments_enabled: boolean;
}

export function getAccessSettings(signal?: AbortSignal): Promise<AccessSettings> {
  return apiGet<AccessSettings>("/settings/access", signal);
}

export function updateAccessSettings(payload: Partial<AccessSettings>): Promise<AccessSettings> {
  return apiPatch<AccessSettings, Partial<AccessSettings>>("/settings/access", payload);
}

export interface BotRequirements {
  channel_required: boolean;
  channel_id: number | null;
  channel_url: string | null;
  trial_channel_guard: boolean;
}

export function getBotRequirements(signal?: AbortSignal): Promise<BotRequirements> {
  return apiGet<BotRequirements>("/settings/bot/requirements", signal);
}

export function updateBotRequirements(payload: BotRequirements): Promise<BotRequirements> {
  return apiPut<BotRequirements, BotRequirements>("/settings/bot/requirements", payload);
}

export function getPaymentWaitlistCount(signal?: AbortSignal): Promise<{ total: number }> {
  return apiGet<{ total: number }>("/transactions/waitlist", signal);
}
