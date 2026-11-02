import { useTranslation } from "react-i18next";

import { withEmphasis } from "@shared/lib/text-emphasis";
import { GuideCopy, GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

export function GithubOAuthGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog
      title={t("settings.oauth.githubGuide.title")}
    >
      <div>
        <GuideHeading>
          {t("settings.oauth.githubGuide.createAppTitle")}
        </GuideHeading>
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
          <GuideCopy
            label={t("settings.oauth.githubGuide.callbackCommentLabel")}
            value={t("settings.oauth.githubGuide.callbackUrlValue")}
          />
        </div>

        <p className="mt-2 text-[12px] text-muted-foreground">
          {t("settings.oauth.githubGuide.callbackNote")}
        </p>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.githubGuide.settingsTitle")}
        </GuideHeading>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.githubGuide.settingsBody"), ["Client ID", "Client secret"])}
        </p>
      </div>
    </GuideDialog>
  );
}
