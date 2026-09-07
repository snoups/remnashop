import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { GuideDialog } from "@shared/ui/GuideDialog";

export function OidcOAuthGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      ariaLabel={t("settings.oauth.guideAriaLabel")}
      title={t("settings.oauth.oidcGuide.title")}
    >
      <div>
        <p>{t("settings.oauth.oidcGuide.intro")}</p>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.oidcGuide.callbackTitle")}
        </h3>
        <p className="mt-2">{t("settings.oauth.oidcGuide.callbackIntro")}</p>

        <div className="mt-3">
          <CopyableValue
            label={t("settings.oauth.oidcGuide.callbackCommentLabel")}
            value={t("settings.oauth.oidcGuide.callbackUrlValue")}
            copyAria={t("settings.oauth.copy")}
          />
        </div>

        <p className="mt-2 text-[12px] text-muted-foreground">
          {t("settings.oauth.oidcGuide.callbackNote")}
        </p>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.oidcGuide.settingsTitle")}
        </h3>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.oidcGuide.settingsBody"), [
            "Issuer URL",
            "Client ID",
            "Client secret",
          ])}
        </p>
      </div>
    </GuideDialog>
  );
}
