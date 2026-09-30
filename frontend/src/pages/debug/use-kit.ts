import { useCallback } from "react";
import { useTranslation } from "react-i18next";

/** t() scoped to debugPage.kit */
export function useKit() {
  const { t } = useTranslation();
  return useCallback((key: string, options?: Record<string, unknown>) => t(`debugPage.kit.${key}`, options), [t]);
}
