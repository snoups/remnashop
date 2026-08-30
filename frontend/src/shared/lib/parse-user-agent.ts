interface ParsedUserAgent {
  browser: string;
  os: string;
}

const BROWSER_PATTERNS: [RegExp, string][] = [
  [/edg\//i, "Edge"],
  [/opr\/|opera/i, "Opera"],
  [/chrome|chromium|crios/i, "Chrome"],
  [/firefox|fxios/i, "Firefox"],
  [/safari/i, "Safari"],
];

const OS_PATTERNS: [RegExp, string][] = [
  [/windows/i, "Windows"],
  [/mac os x|macintosh/i, "macOS"],
  [/android/i, "Android"],
  [/iphone|ipad|ipod/i, "iOS"],
  [/linux/i, "Linux"],
];

function match(patterns: [RegExp, string][], ua: string): string | null {
  for (const [pattern, label] of patterns) {
    if (pattern.test(ua)) return label;
  }
  return null;
}

export function parseUserAgent(ua: string | null): ParsedUserAgent {
  if (!ua) return { browser: "Unknown", os: "Unknown" };
  return {
    browser: match(BROWSER_PATTERNS, ua) ?? "Unknown",
    os: match(OS_PATTERNS, ua) ?? "Unknown",
  };
}
