import { ArrowRight, Check, PiggyBank, Wallet } from "lucide-react";
import { motion, type Variants } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap } from "@shared/lib/bounceState";
import { BOOSTY_URL, TELEGRAM_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { TelegramIcon } from "@shared/ui/BrandIcons";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { Button } from "@shared/ui/Button";
import { LabeledDivider } from "@shared/ui/LabeledDivider";

interface WelcomeDonateDialogProps {
  onContinue: () => void;
}

const donatePillClassName =
  "flex flex-1 items-center justify-center gap-1.5 rounded-full border border-border h-9 px-3 text-sm font-medium text-muted-foreground transition-colors hover:border-glass-border hover:bg-white/[0.06] hover:text-primary";

const EASE_OUT: [number, number, number, number] = [0.2, 0.8, 0.2, 1];
const EASE_POP: [number, number, number, number] = [0.34, 1.56, 0.64, 1];

const CARD_VARIANTS: Variants = {
  hidden: { opacity: 0, scale: 0.96, filter: "blur(8px)" },
  shown: { opacity: 1, scale: 1, filter: "blur(0px)", transition: { duration: 0.45, ease: EASE_OUT } },
  leave: { opacity: 0, transition: { duration: 0.25, ease: "easeIn" } },
};

function riseIn(delay: number) {
  return {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { delay, duration: 0.4, ease: EASE_OUT },
  };
}

export function WelcomeDonateDialog({ onContinue }: WelcomeDonateDialogProps) {
  const { t } = useTranslation();

  const [isLeaving, setIsLeaving] = useState(false);

  const tapProps = bounceTap(0.12);

  return (
    <DialogPortal>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          className="flex w-full max-w-md flex-col items-center gap-6 rounded-2xl border border-glass-border bg-surface/40 p-8 text-center shadow-2xl backdrop-blur-xl"
          variants={CARD_VARIANTS}
          initial="hidden"
          animate={isLeaving ? "leave" : "shown"}
          onAnimationComplete={(definition) => definition === "leave" && onContinue()}
        >
          <div className="relative">
            <motion.div
              className="flex size-[72px] items-center justify-center rounded-full border border-primary/40 bg-accent shadow-[0_0_46px_color-mix(in_srgb,var(--color-primary)_28%,transparent)]"
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.12, duration: 0.6, ease: EASE_POP }}
            >
              <BrandLogo className="size-8 text-primary" />
            </motion.div>
            {/* one-shot glow burst once the logo has landed */}
            <motion.span
              className="pointer-events-none absolute inset-0 rounded-full border border-primary/60"
              initial={{ opacity: 0, scale: 1 }}
              animate={{ opacity: [0.7, 0], scale: [1, 1.7] }}
              transition={{ delay: 0.7, duration: 1.1, ease: "easeOut" }}
            />
            <motion.div
              className="absolute -bottom-1 -right-1 flex size-[22px] items-center justify-center rounded-full border-[3px] border-[#1c1e24] bg-success"
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.55, duration: 0.4, ease: EASE_POP }}
            >
              <Check className="size-[11px] text-primary-foreground" strokeWidth={3} />
            </motion.div>
          </div>

          <motion.div className="flex flex-col gap-2" {...riseIn(0.5)}>
            <h1 className="text-xl font-bold text-foreground">{t("auth.welcome.title")}</h1>
            <p className="text-sm text-muted-foreground">{t("auth.welcome.description")}</p>
          </motion.div>

          <motion.div className="w-full" {...riseIn(0.6)}>
            <Button
              variant="solid"
              className="w-full"
              type="button"
              onClick={() => setIsLeaving(true)}
              {...tapProps}
            >
              {t("auth.welcome.continueButton")}
              <ArrowRight className="size-4" />
            </Button>
          </motion.div>

          <motion.div className="flex w-full flex-col gap-3" {...riseIn(0.7)}>
            <LabeledDivider>{t("donate.title")}</LabeledDivider>

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
          </motion.div>
        </motion.div>
      </div>
    </DialogPortal>
  );
}
