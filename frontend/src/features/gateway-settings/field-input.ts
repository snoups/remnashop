import type { GatewayFieldSpec } from "@entities/gateways/api";

const PEM_FIELD_KEYS = new Set(["private_key", "public_key"]);
const MAX_CURRENCY_LENGTH = 10;

/** Drops characters the field can never legitimately contain, so typing and pasting both stay clean. */
export function sanitizeFieldValue(field: GatewayFieldSpec, value: string): string {
  if (field.kind === "number") return value.replace(/\D/g, "");
  if (field.key === "currency") {
    return value.replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, MAX_CURRENCY_LENGTH);
  }
  if (PEM_FIELD_KEYS.has(field.key)) return value.replace(/[\r\n]/g, "");
  return value.replace(/\s/g, "");
}

export function inputModeFor(field: GatewayFieldSpec): "numeric" | "text" {
  return field.kind === "number" ? "numeric" : "text";
}
