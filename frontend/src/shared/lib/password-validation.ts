// Mirrors the backend's validation (core/security/password.py's PASSWORD_PATTERN)
// for instant feedback; the server remains the source of truth.
export const PASSWORD_PATTERN = /^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).{24,}$/;
