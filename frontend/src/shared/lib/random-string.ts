// Rejection sampling instead of `byte % charset.length`: a plain modulo skews
// toward the low end of the charset whenever 256 isn't a multiple of its
// length (true for any charset not sized as a power of two) -- rejecting the
// spillover bytes keeps every index uniformly likely.
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
