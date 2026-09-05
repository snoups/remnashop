import { ArrowRight, Check, PiggyBank, Wallet } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BOOSTY_URL, TELEGRAM_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { TelegramIcon } from "@shared/ui/BrandIcons";

interface WelcomeDonateDialogProps {
  onContinue: () => void;
}

const donatePillClassName =
  "flex flex-1 items-center justify-center gap-1.5 rounded-full border border-border px-3 py-2 text-[13px] font-medium text-muted-foreground transition-colors hover:border-glass-border hover:bg-white/[0.06] hover:text-primary";

export function WelcomeDonateDialog({ onContinue }: WelcomeDonateDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const tapProps = bounceTap(bounceStrength, 0.12);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-3xl">
      <div className="flex w-full max-w-md flex-col items-center gap-6 rounded-2xl border border-glass-border bg-surface/40 p-8 text-center shadow-2xl backdrop-blur-xl">
        <div className="relative">
          <div className="flex size-[72px] items-center justify-center rounded-full border border-primary/40 bg-accent shadow-[0_0_46px_rgba(34,211,238,0.28)]">
            <BrandLogo className="size-8 text-primary" />
          </div>
          <div className="absolute -bottom-1 -right-1 flex size-[22px] items-center justify-center rounded-full border-[3px] border-[#1c1e24] bg-success">
            <Check className="size-[11px] text-primary-foreground" strokeWidth={3} />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <h1 className="text-xl font-bold text-foreground">{t("auth.welcome.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("auth.welcome.description")}</p>
        </div>

        <motion.button
          type="button"
          onClick={onContinue}
          {...tapProps}
          className="flex w-full items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 font-semibold text-primary-foreground transition hover:bg-primary-hover"
        >
          {t("auth.welcome.continueButton")}
          <ArrowRight className="size-4" />
        </motion.button>

        <div className="flex w-full flex-col gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-px flex-1 bg-border" />
            <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("donate.title")}
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <div className="flex w-full gap-2">
            <motion.a href={BOOSTY_URL} target="_blank" rel="noreferrer" {...tapProps} className={donatePillClassName}>
              <PiggyBank className="size-[15px]" />
              {t("donate.boostyLabel")}
            </motion.a>
            <motion.a href={YOOKASSA_URL} target="_blank" rel="noreferrer" {...tapProps} className={donatePillClassName}>
              <Wallet className="size-[15px]" />
              {t("donate.yookassaLabel")}
            </motion.a>
            <motion.a href={TELEGRAM_URL} target="_blank" rel="noreferrer" {...tapProps} className={donatePillClassName}>
              <TelegramIcon className="size-[15px]" />
              {t("buildInfo.telegramButton")}
            </motion.a>
          </div>
        </div>
      </div>
    </div>
  );
}
