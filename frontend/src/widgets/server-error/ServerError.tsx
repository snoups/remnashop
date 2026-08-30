import { ServerCrash } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

export function ServerError() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-glass-border bg-surface/40 p-8 text-center shadow-2xl backdrop-blur-xl">
        <ServerCrash className="size-12 shrink-0 text-error" />
        <div>
          <h1 className="text-lg font-bold text-foreground">{t("errors.serverErrorTitle")}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{t("errors.serverErrorDescription")}</p>
        </div>
        <motion.button
          type="button"
          onClick={() => window.location.reload()}
          {...bounceTap(bounceStrength)}
          className="mt-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary-hover"
        >
          {t("errors.retry")}
        </motion.button>
      </div>
    </div>
  );
}
