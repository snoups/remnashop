import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

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
        <GuideHeading>
          {t("settings.oauth.passkeyGuide.rpIdTitle")}
        </GuideHeading>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.passkeyGuide.rpIdBody"), "example.com")}
        </p>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.passkeyGuide.originTitle")}
        </GuideHeading>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.passkeyGuide.originBody"), "https://example.com")}
        </p>
      </div>
    </GuideDialog>
  );
}
