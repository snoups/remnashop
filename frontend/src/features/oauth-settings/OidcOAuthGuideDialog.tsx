import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { GuideCopy, GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

export function OidcOAuthGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      title={t("settings.oauth.oidcGuide.title")}
    >
      <div>
        <p>{t("settings.oauth.oidcGuide.intro")}</p>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.oidcGuide.callbackTitle")}
        </GuideHeading>
        <p className="mt-2">{t("settings.oauth.oidcGuide.callbackIntro")}</p>

        <div className="mt-3">
          <GuideCopy
            label={t("settings.oauth.oidcGuide.callbackCommentLabel")}
            value={t("settings.oauth.oidcGuide.callbackUrlValue")}
          />
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          {t("settings.oauth.oidcGuide.callbackNote")}
        </p>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.oidcGuide.settingsTitle")}
        </GuideHeading>
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
