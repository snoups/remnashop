// ChipsInput normalizers: the stored form of a token, or null when it isn't valid
const EMAIL_PATTERN = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

export const normalizePositiveInt = (token: string): string | null =>
  /^\d+$/.test(token) && Number(token) > 0 ? String(Number(token)) : null;

// kept as typed: plan access compares emails case-sensitively
export const normalizeEmail = (token: string): string | null => (EMAIL_PATTERN.test(token) ? token : null);
