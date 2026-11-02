import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { withEmphasis, withLink } from "@shared/lib/text-emphasis";
import { GuideCopy, GuideDialog, GuideHeading, GuideTip } from "@shared/ui/glass/GuideDialog";

// Step 5's second sentence (the fallback note) is italicized; the first sentence
// still gets the "Switch to OpenID Connect Login" code emphasis.
function renderSwitchStep(step: string): ReactNode {
  const separatorIndex = step.indexOf(". ");
  if (separatorIndex === -1) return withEmphasis(step, "Switch to OpenID Connect Login");

  const mainSentence = step.slice(0, separatorIndex);
  const restSentence = step.slice(separatorIndex + 2);
  return (
    <>
      {withEmphasis(mainSentence, "Switch to OpenID Connect Login")}
      <span className="mt-1 block italic text-muted-foreground">{restSentence}</span>
    </>
  );
}

export function TelegramOAuthGuideDialog() {
  const { t } = useTranslation();

  const botSetupSteps = t("settings.oauth.telegramGuide.botSetupSteps", {
    returnObjects: true,
  }) as string[];
  const accessSetupSteps = t("settings.oauth.telegramGuide.accessSetupSteps", {
    returnObjects: true,
  }) as string[];

  return (
    <GuideDialog
      title={t("settings.oauth.telegramGuide.title")}
    >
      <p>{t("settings.oauth.telegramGuide.intro")}</p>

      <div>
        <GuideHeading>
          {t("settings.oauth.telegramGuide.botSetupTitle")}
        </GuideHeading>
        <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-5">
          {botSetupSteps.map((step, index) => (
            <li key={index}>
              {index === 0 && withLink(step, "@BotFather", "https://t.me/botfather")}
              {index === 2 && withEmphasis(step, "Login Widget")}
              {index === 4 && renderSwitchStep(step)}
              {index === 5 && withEmphasis(step, ["Add a Redirect URI", "Add a Trusted Origin"])}
              {index !== 0 && index !== 2 && index !== 4 && index !== 5 && step}
            </li>
          ))}
        </ol>
        <div className="mt-3 flex flex-col gap-2">
          <GuideCopy
            label={t("settings.oauth.telegramGuide.trustedOriginsLabel")}
            value={t("settings.oauth.telegramGuide.trustedOriginsValue")}
          />
          <GuideCopy
            label={t("settings.oauth.telegramGuide.redirectUrisLabel")}
            value={t("settings.oauth.telegramGuide.redirectUrisValue")}
          />
        </div>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.telegramGuide.accessSetupTitle")}
        </GuideHeading>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.telegramGuide.accessSetupIntro"), [
            "Client ID",
            "Client secret",
          ])}
        </p>
        <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-5">
          {accessSetupSteps.map((step, index) => (
            <li key={index}>
              {index === 0 ? withLink(step, "@Get_myidrobot", "https://t.me/Get_myidrobot") : step}
            </li>
          ))}
        </ol>
      </div>

      <div>
        <GuideHeading>
          {t("settings.oauth.telegramGuide.knownIssuesTitle")}
        </GuideHeading>
        <p className="mt-2">
          {withEmphasis(t("settings.oauth.telegramGuide.knownIssuesIntro"), "Telegram OAuth2")}
        </p>
        <GuideTip className="mt-2">
          {t("settings.oauth.telegramGuide.knownIssuesProxyTip")}
        </GuideTip>

        <div className="mt-3 flex flex-col gap-3">
          <div>
            <p className="font-semibold text-error">
              {t("settings.oauth.telegramGuide.errorBotDomainTitle")}
            </p>
            <p className="mt-1">{t("settings.oauth.telegramGuide.errorBotDomainBody")}</p>
          </div>
          <div>
            <p className="font-semibold text-error">
              {t("settings.oauth.telegramGuide.errorNoCodeTitle")}
            </p>
            <p className="mt-1">
              {withLink(t("settings.oauth.telegramGuide.errorNoCodeBody"), "fragment.com", "https://fragment.com")}
            </p>
          </div>
        </div>
      </div>
    </GuideDialog>
  );
}
