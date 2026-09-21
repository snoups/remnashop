export const TELEGRAM_URL = "https://t.me/remna_shop";
export const BOOSTY_URL = "https://boosty.to/snoups";
export const YOOKASSA_URL = "https://yookassa.ru/my/i/Z8AkHJ_F9sO_/l";
export const COMMUNITY_URL = "https://boosty.to/snoups/purchase/3778398?share=subscription_link";

/** GitHub API base for a repo, given its https://github.com/<owner>/<repo> URL. */
export function githubApiUrl(repositoryUrl: string, suffix = ""): string {
  const path = new URL(repositoryUrl).pathname.replace(/^\//, "");
  return `https://api.github.com/repos/${path}${suffix}`;
}

/**
 * True only for an absolute https:// URL. The OAuth authorization endpoint the
 * API returns comes from the configured issuer's discovery document, so it is
 * attacker-influenced; assigning it to window.location.href without this check
 * would let a javascript: value run in the dashboard origin.
 */
export function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}
