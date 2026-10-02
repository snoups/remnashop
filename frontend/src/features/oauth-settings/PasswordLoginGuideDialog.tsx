import { useTranslation } from "react-i18next";

import { CopyableValue } from "@shared/ui/CopyableValue";
import { GuideDialog } from "@shared/ui/GuideDialog";

export function PasswordLoginGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      title={t("settings.oauth.passwordLoginGuide.title")}
    >
      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.passwordLoginGuide.rescueTitle")}
        </h3>
        <p className="mt-2">{t("settings.oauth.passwordLoginGuide.rescueIntro")}</p>

        <div className="mt-3">
          <CopyableValue
            label={t("settings.oauth.passwordLoginGuide.rescueCommandLabel")}
            value={t("settings.oauth.passwordLoginGuide.rescueCommandValue")}
          />
        </div>

        <p className="mt-2 text-[12px] text-muted-foreground">
          {t("settings.oauth.passwordLoginGuide.rescueNote")}
        </p>
      </div>
    </GuideDialog>
  );
}
