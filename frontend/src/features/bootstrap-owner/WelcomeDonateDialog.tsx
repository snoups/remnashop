import { PiggyBank, Wallet } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BOOSTY_URL, TELEGRAM_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { TelegramIcon } from "@shared/ui/BrandIcons";

interface WelcomeDonateDialogProps {
  onContinue: () => void;
}

export function WelcomeDonateDialog({ onContinue }: WelcomeDonateDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const tapProps = bounceTap(bounceStrength, 0.12);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-3xl">
      <div className="flex w-full max-w-md flex-col items-center gap-6 text-center">
        <BrandLogo className="size-12 text-primary" />

        <div className="flex flex-col gap-2">
          <h1 className="text-xl font-bold text-foreground">{t("auth.welcome.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("auth.welcome.description")}</p>
        </div>

        <div className="flex w-full gap-2">
          <motion.a
            href={BOOSTY_URL}
            target="_blank"
            rel="noreferrer"
            {...tapProps}
            className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
          >
            <PiggyBank className="size-4" />
            {t("donate.boostyLabel")}
          </motion.a>
          <motion.a
            href={YOOKASSA_URL}
            target="_blank"
            rel="noreferrer"
            {...tapProps}
            className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
          >
            <Wallet className="size-4" />
            {t("donate.yookassaLabel")}
          </motion.a>
          <motion.a
            href={TELEGRAM_URL}
            target="_blank"
            rel="noreferrer"
            {...tapProps}
            className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
          >
            <TelegramIcon className="size-4" />
            {t("buildInfo.telegramButton")}
          </motion.a>
        </div>

        <motion.button
          type="button"
          onClick={onContinue}
          {...tapProps}
          className="w-full rounded-full bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:bg-primary-hover"
        >
          {t("auth.welcome.continueButton")}
        </motion.button>
      </div>
    </div>
  );
}
