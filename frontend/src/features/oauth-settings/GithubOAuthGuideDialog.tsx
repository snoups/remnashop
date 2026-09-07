import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { GuideDialog } from "@shared/ui/GuideDialog";

export function GithubOAuthGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      ariaLabel={t("settings.oauth.guideAriaLabel")}
      title={t("settings.oauth.githubGuide.title")}
    >
      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.githubGuide.createAppTitle")}
        </h3>
        <p className="mt-2">
          {t("settings.oauth.githubGuide.createAppIntro")}{" "}
          <a
            href="https://github.com/settings/applications/new"
            target="_blank"
            rel="noreferrer"
            className="text-primary hover:underline"
          >
            github.com/settings/applications/new
          </a>
        </p>

        <p className="mt-3">
          {withEmphasis(t("settings.oauth.githubGuide.callbackIntro"), "Authorization callback URL")}
        </p>

        <div className="mt-3">
          <CopyableValue
            label={t("settings.oauth.githubGuide.callbackCommentLabel")}
            value={t("settings.oauth.githubGuide.callbackUrlValue")}
            copyAria={t("settings.oauth.copy")}
          />
        </div>

        <p className="mt-2 text-[12px] text-muted-foreground">
          {t("settings.oauth.githubGuide.callbackNote")}
        </p>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">
          {t("settings.oauth.githubGuide.settingsTitle")}
        </h3>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.githubGuide.settingsBody"), ["Client ID", "Client secret"])}
        </p>
      </div>
    </GuideDialog>
  );
}
