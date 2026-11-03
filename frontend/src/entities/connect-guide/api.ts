import { apiGet, apiPost, apiPut } from "@shared/api/http";

export const PLATFORM_IDS = ["ios", "android", "windows", "macos", "linux", "androidtv", "appletv"] as const;
export type PlatformId = (typeof PLATFORM_IDS)[number];

export const STEP_ICONS = ["download", "plus", "power", "settings", "check", "link", "qr", "info", "shield", "globe"] as const;
export type StepIcon = (typeof STEP_ICONS)[number];

export const SUBSCRIPTION_LINK_TOKEN = "{{SUBSCRIPTION_LINK}}";

/** locale → text */
export type LocalizedText = Record<string, string>;

export type ConnectButton =
  | { kind: "external"; label: LocalizedText; url: string }
  | { kind: "deep_link"; label: LocalizedText; template: string; encode?: "raw" | "component"}
  | { kind: "copy_link"; label: LocalizedText };

export interface ConnectStep {
  title: LocalizedText;
  body: LocalizedText | null;
  icon: StepIcon;
  buttons: ConnectButton[];
}

export interface ConnectApp {
  id: string;
  name: string;
  featured: boolean;
  steps: ConnectStep[];
}

export interface ConnectPlatform {
  id: PlatformId;
  apps: ConnectApp[];
}

export interface ConnectCatalog {
  platforms: ConnectPlatform[];
}

export interface ConnectGuide {
  enabled: boolean;
  catalog: ConnectCatalog;
  is_default: boolean;
}

export type SaveConnectGuideRequest = Omit<ConnectGuide, "is_default">;

export function getConnectGuide(signal?: AbortSignal): Promise<ConnectGuide> {
  return apiGet<ConnectGuide>("/connect-guide", signal);
}

export function saveConnectGuide(payload: SaveConnectGuideRequest): Promise<ConnectGuide> {
  return apiPut<ConnectGuide, SaveConnectGuideRequest>("/connect-guide", payload);
}

export function resetConnectGuide(): Promise<ConnectGuide> {
  return apiPost<ConnectGuide, Record<string, never>>("/connect-guide/actions/reset", {});
}
