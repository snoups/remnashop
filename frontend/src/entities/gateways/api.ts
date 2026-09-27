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
  webhook_url: string | null;
  fields: GatewayFieldSpec[];
}

interface GatewayCatalogResponse {
  entries: GatewayCatalogEntry[];
}

export function listGateways(signal?: AbortSignal): Promise<Gateway[]> {
  return apiGet<Gateway[]>("/gateways", signal);
}

export function getGatewayCatalog(signal?: AbortSignal): Promise<GatewayCatalogEntry[]> {
  return apiGet<GatewayCatalogResponse>("/gateways/catalog", signal).then(
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

export interface TestPayment {
  order_id: number;
  confirmation_url: string | null;
}

export type TestPaymentStatus = "PENDING" | "PAID" | "FAILED" | "CANCELED" | "REFUNDED";

export function createTestPayment(type: string): Promise<TestPayment> {
  return apiPost<TestPayment, Record<string, never>>(`/gateways/${type}/test`, {});
}

export function getTestPaymentStatus(orderId: number): Promise<{ status: TestPaymentStatus }> {
  return apiGet<{ status: TestPaymentStatus }>(`/gateways/test-payments/${orderId}`);
}

export function reorderGateways(types: string[]): Promise<Gateway[]> {
  return apiPut<Gateway[], { types: string[] }>("/gateways/order", { types });
}
