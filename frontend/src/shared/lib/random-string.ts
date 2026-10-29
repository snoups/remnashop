// Rejection sampling, not `byte % charset.length`: modulo favours the start of
// the charset unless its length divides 256.
function randomIndex(max: number): number {
  const limit = 256 - (256 % max);
  const bytes = new Uint8Array(1);
  let value: number;
  do {
    crypto.getRandomValues(bytes);
    value = bytes[0]!;
  } while (value >= limit);
  return value % max;
}

// crypto.randomUUID exists only in a secure context; plain HTTP gets Math.random
export function randomId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(16).slice(2).padEnd(32, "0");
}

export function randomString(charset: string, length: number): string {
  return Array.from({ length }, () => charset[randomIndex(charset.length)]).join("");
}
