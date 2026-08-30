import { apiGet, apiPost, apiPut } from "@shared/api/http";

export interface Gateway {
  type: string;
  order_index: number;
  is_active: boolean;
  is_configured: boolean;
}

export type GatewayFieldKind = "text" | "secret" | "number";

export interface GatewayFieldSpec {
  key: string;
  kind: GatewayFieldKind;
  required: boolean;
}

export interface GatewayCatalogEntry {
  type: string;
  fields: GatewayFieldSpec[];
}

interface GatewayCatalogResponse {
  entries: GatewayCatalogEntry[];
}

export function listGateways(): Promise<Gateway[]> {
  return apiGet<Gateway[]>("/gateways");
}

export function getGatewayCatalog(): Promise<GatewayCatalogEntry[]> {
  return apiGet<GatewayCatalogResponse>("/gateways/catalog").then(
    (response) => response.entries,
  );
}

export function updateGatewaySettings(
  type: string,
  values: Record<string, string>,
): Promise<Gateway> {
  return apiPut<Gateway, { values: Record<string, string> }>(`/gateways/${type}/settings`, {
    values,
  });
}

export function toggleGatewayActive(type: string): Promise<Gateway> {
  return apiPost<Gateway, Record<string, never>>(`/gateways/${type}/toggle`, {});
}

export function reorderGateways(types: string[]): Promise<Gateway[]> {
  return apiPut<Gateway[], { types: string[] }>("/gateways/order", { types });
}
