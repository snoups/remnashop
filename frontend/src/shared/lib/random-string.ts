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

export function randomString(charset: string, length: number): string {
  return Array.from({ length }, () => charset[randomIndex(charset.length)]).join("");
}
