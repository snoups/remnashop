import { randomString } from "@shared/lib/random-string";

// Mirrors the backend's validation (core/security/password.py's PASSWORD_PATTERN)
// for instant feedback; the server remains the source of truth.
export const PASSWORD_PATTERN = /^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).{24,}$/;

const PASSWORD_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const GENERATED_PASSWORD_LENGTH = 32;

// Retries on a miss instead of forcing characters into positions, so the draw
// stays uniform; at 32 characters a retry almost never happens.
export function generatePassword(): string {
  let candidate: string;
  do {
    candidate = randomString(PASSWORD_CHARSET, GENERATED_PASSWORD_LENGTH);
  } while (!PASSWORD_PATTERN.test(candidate));
  return candidate;
}
