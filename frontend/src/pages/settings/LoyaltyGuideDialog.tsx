import { useTranslation } from "react-i18next";

import { GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

const SECTIONS = ["tiers", "window", "combine", "recalculation", "exclude"] as const;

export function LoyaltyGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog header title={t("loyalty.settings.guide.title")}>
      <div>
        <p>{t("loyalty.settings.guide.intro")}</p>
      </div>

      {SECTIONS.map((section) => (
        <div key={section}>
          <GuideHeading>{t(`loyalty.settings.guide.${section}Title`)}</GuideHeading>
          <p className="mt-2">{t(`loyalty.settings.guide.${section}Body`)}</p>
          <p className="mt-2 text-muted-foreground">{t(`loyalty.settings.guide.${section}Example`)}</p>
        </div>
      ))}
    </GuideDialog>
  );
}
