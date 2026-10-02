import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { GuideDialog } from "@shared/ui/GuideDialog";

export function PasskeyGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      title={t("settings.oauth.passkeyGuide.title")}
    >
      <div>
        <p>{t("settings.oauth.passkeyGuide.intro")}</p>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.passkeyGuide.rpIdTitle")}
        </h3>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.passkeyGuide.rpIdBody"), "example.com")}
        </p>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.passkeyGuide.originTitle")}
        </h3>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.passkeyGuide.originBody"), "https://example.com")}
        </p>
      </div>
    </GuideDialog>
  );
}
