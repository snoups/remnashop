import { useTranslation } from "react-i18next";

import { GuideDialog, GuideHeading, GuideTip } from "@shared/ui/glass/GuideDialog";

const SECTIONS = ["calculation", "anchorColumn", "pin", "bulk", "anchorSwitch"] as const;

export function PricingGuideDialog() {
  const { t } = useTranslation();

  return (
    <GuideDialog header title={t("pricing.matrix.guide.title")}>
      <div>
        <p>{t("pricing.matrix.guide.intro")}</p>
        <GuideTip className="mt-3">{t("pricing.matrix.guide.saveTip")}</GuideTip>
      </div>

      {SECTIONS.map((section) => (
        <div key={section}>
          <GuideHeading>{t(`pricing.matrix.guide.${section}Title`)}</GuideHeading>
          <p className="mt-2">{t(`pricing.matrix.guide.${section}Body`)}</p>
          <p className="mt-2 text-muted-foreground">{t(`pricing.matrix.guide.${section}Example`)}</p>
        </div>
      ))}
    </GuideDialog>
  );
}
