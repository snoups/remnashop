import { apiGet, apiPost, apiPut } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export interface Gateway {
  type: string;
  order_index: number;
  is_active: boolean;
  is_configured: boolean;
  /** current state of the gateway's boolean settings, the only readable ones */
  flags: Record<string, boolean>;
}

export type GatewayFieldKind = "text" | "secret" | "number" | "boolean" | "choice";

export interface GatewayFieldSpec {
  key: string;
  kind: GatewayFieldKind;
  required: boolean;
  options: string[];
}

export interface GatewayCatalogEntry {
  type: string;
  webhook_url: string | null;
  fields: GatewayFieldSpec[];
}

interface GatewayCatalogResponse {
  items: GatewayCatalogEntry[];
  total: number;
}

export function listGateways(signal?: AbortSignal): Promise<Gateway[]> {
  return apiGet<ListResponse<Gateway>>("/gateways", signal).then((response) => response.items);
}

export function getGatewayCatalog(signal?: AbortSignal): Promise<GatewayCatalogEntry[]> {
  return apiGet<GatewayCatalogResponse>("/gateways/catalog", signal).then(
    (response) => response.items,
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

export function setGatewayActive(type: string, active: boolean): Promise<Gateway> {
  const action = active ? "enable" : "disable";
  return apiPost<Gateway, Record<string, never>>(`/gateways/${type}/actions/${action}`, {});
}

export interface TestPayment {
  order_id: number;
  confirmation_url: string | null;
}

export type TestPaymentStatus = "PENDING" | "PAID" | "FAILED" | "CANCELED" | "REFUNDED";

export function createTestPayment(type: string): Promise<TestPayment> {
  return apiPost<TestPayment, { gateway_type: string }>("/transactions/test-payments", {
    gateway_type: type,
  });
}

export function getTestPaymentStatus(orderId: number): Promise<{ status: TestPaymentStatus }> {
  return apiGet<{ status: TestPaymentStatus }>(`/transactions/test-payments/${orderId}`);
}

/** @public reorder UI not built yet */
export function reorderGateways(types: string[]): Promise<Gateway[]> {
  return apiPost<ListResponse<Gateway>, { types: string[] }>("/gateways/actions/reorder", { types }).then(
    (response) => response.items,
  );
}
