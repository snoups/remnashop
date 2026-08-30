import { Compass } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

const MotionLink = motion.create(Link);

export function NotFoundPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const brandName = useBrandName();
  useDocumentTitle(brandName, t("errors.notFoundTitle"));

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-glass-border bg-surface/40 p-8 text-center shadow-2xl backdrop-blur-xl">
        <Compass className="size-12 shrink-0 text-primary" />
        <div>
          <span className="font-mono text-3xl font-bold tracking-tight text-foreground">404</span>
          <h1 className="mt-1 text-lg font-bold text-foreground">{t("errors.notFoundTitle")}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{t("errors.notFoundDescription")}</p>
        </div>
        <MotionLink
          to="/"
          {...bounceTap(bounceStrength)}
          className="mt-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary-hover"
        >
          {t("errors.notFoundButton")}
        </MotionLink>
      </div>
    </div>
  );
}
