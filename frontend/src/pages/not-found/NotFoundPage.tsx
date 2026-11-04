import { Compass } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useBrandName } from "@entities/appearance/use-appearance";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { FULL_SCREEN_ACTION_CLASS, FullScreenMessage } from "@widgets/full-screen-message/FullScreenMessage";
import { Pressable } from "@shared/ui/Pressable";

export function NotFoundPage() {
  const { t } = useTranslation();
  const brandName = useBrandName();
  useDocumentTitle(brandName, t("errors.notFoundTitle"));

  return (
    <FullScreenMessage
      icon={Compass}
      tone="primary"
      code="404"
      title={t("errors.notFoundTitle")}
      description={t("errors.notFoundDescription")}
      action={
        <Pressable as="link" to="/" className={FULL_SCREEN_ACTION_CLASS}>
          {t("errors.notFoundButton")}
        </Pressable>
      }
    />
  );
}
