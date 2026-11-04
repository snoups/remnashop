import { apiGet, apiPut } from "@shared/api/http";

export interface SecuritySettings {
  ip_allowlist: string[];
  /** this request's address, as the allowlist check sees it */
  client_ip: string;
}

export function getOwnSecurity(signal?: AbortSignal): Promise<SecuritySettings> {
  return apiGet<SecuritySettings>("/users/me/security", signal);
}

export function updateOwnSecurity(ipAllowlist: string[]): Promise<SecuritySettings> {
  return apiPut<SecuritySettings, { ip_allowlist: string[] }>("/users/me/security", {
    ip_allowlist: ipAllowlist,
  });
}

const IPV4_PATTERN = /^(\d{1,3}\.){3}\d{1,3}$/;

/** Mirrors the backend's ipaddress.ip_network(entry, strict=False): an address, optionally with a prefix. */
export function isIpOrNetwork(entry: string): boolean {
  const [address, prefix, ...rest] = entry.split("/");
  if (rest.length > 0) return false;
  const isV6 = address.includes(":");
  if (prefix !== undefined && !(/^\d{1,3}$/.test(prefix) && Number(prefix) <= (isV6 ? 128 : 32))) return false;
  try {
    // the URL parser validates IPv6 and rejects octets over 255; a hostname that
    // comes back changed means leading zeros or a shorthand like "10.1"
    if (isV6) return Boolean(new URL(`http://[${address}]`).hostname);
    return IPV4_PATTERN.test(address) && new URL(`http://${address}`).hostname === address;
  } catch {
    return false;
  }
}

export function parseEntries(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function ipv4ToNumber(address: string): number | null {
  if (!IPV4_PATTERN.test(address)) return null;
  const octets = address.split(".").map(Number);
  if (octets.some((octet) => octet > 255)) return null;
  return octets.reduce((total, octet) => total * 256 + octet, 0);
}

/** Whether the list lets this IP in: an exact entry, or an IPv4 network around it (IPv6 networks aren't matched). */
export function isIpCovered(ip: string, entries: string[]): boolean {
  const address = ipv4ToNumber(ip);
  return entries.some((entry) => {
    if (entry === ip) return true;
    const [network, prefix] = entry.split("/");
    const base = ipv4ToNumber(network);
    if (address === null || base === null || prefix === undefined) return false;
    const block = 2 ** (32 - Number(prefix));
    return Math.floor(address / block) === Math.floor(base / block);
  });
}
