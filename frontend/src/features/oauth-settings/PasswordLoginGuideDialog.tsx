import { useTranslation } from "react-i18next";

import { GuideCopy, GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

export function PasswordLoginGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      title={t("settings.oauth.passwordLoginGuide.title")}
    >
      <div>
        <GuideHeading>
          {t("settings.oauth.passwordLoginGuide.rescueTitle")}
        </GuideHeading>
        <p className="mt-2">{t("settings.oauth.passwordLoginGuide.rescueIntro")}</p>

        <div className="mt-3">
          <GuideCopy
            label={t("settings.oauth.passwordLoginGuide.rescueCommandLabel")}
            value={t("settings.oauth.passwordLoginGuide.rescueCommandValue")}
          />
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          {t("settings.oauth.passwordLoginGuide.rescueNote")}
        </p>
      </div>
    </GuideDialog>
  );
}
