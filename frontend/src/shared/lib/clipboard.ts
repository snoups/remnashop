import i18n from "@shared/i18n";
import { toast } from "@shared/lib/toast";

/** Resolves false (and says so in a toast) when the clipboard API is missing --
 * a dashboard served over plain HTTP has none -- or the browser denies it, so a
 * caller shows "copied" only for a copy that happened. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    toast.error(i18n.t("app.copyFailed"));
    return false;
  }
}
