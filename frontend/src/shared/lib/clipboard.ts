import i18n from "@shared/i18n";
import { toast } from "@shared/lib/toast";

/** Resolves false (with a toast) when the clipboard API is missing (plain HTTP)
 * or denied, so callers show "copied" only for a real copy. */
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
