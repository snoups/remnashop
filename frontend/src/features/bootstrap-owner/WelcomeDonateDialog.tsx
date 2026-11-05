import { ArrowRight, Check, PiggyBank, Wallet } from "lucide-react";
import { motion, type Variants } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { BOOSTY_URL, TELEGRAM_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { TelegramIcon } from "@shared/ui/BrandIcons";
import { GLASS_LINK_BUTTON_CLASS, GLASS_STANDALONE_CARD_CLASS, SCREEN_TITLE_CLASS } from "@shared/ui/classes";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { Button } from "@shared/ui/Button";
import { LabeledDivider } from "@shared/ui/LabeledDivider";
import { Pressable } from "@shared/ui/Pressable";

interface WelcomeDonateDialogProps {
  onContinue: () => void;
}

const EASE_OUT: [number, number, number, number] = [0.2, 0.8, 0.2, 1];
const EASE_POP: [number, number, number, number] = [0.34, 1.56, 0.64, 1];

const CARD_VARIANTS: Variants = {
  hidden: { opacity: 0, scale: 0.96, filter: "blur(8px)" },
  shown: {
    opacity: 1,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: 0.45, ease: EASE_OUT },
    // a leftover filter keeps the card on its own layer and softens its text
    transitionEnd: { filter: "none" },
  },
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


  return (
    <DialogPortal>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          className={`flex w-full max-w-md flex-col items-center gap-6 text-center ${GLASS_STANDALONE_CARD_CLASS}`}
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
              className="absolute -bottom-1 -right-1 flex size-[22px] items-center justify-center rounded-full border-[3px] border-canvas bg-success"
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.55, duration: 0.4, ease: EASE_POP }}
            >
              <Check className="size-[11px] text-primary-foreground" strokeWidth={3} />
            </motion.div>
          </div>

          <motion.div className="flex flex-col gap-2" {...riseIn(0.5)}>
            <h1 className={SCREEN_TITLE_CLASS}>{t("auth.welcome.title")}</h1>
            <p className="text-[13px] text-muted-foreground">{t("auth.welcome.description")}</p>
          </motion.div>

          <motion.div className="w-full" {...riseIn(0.6)}>
            <Button
              variant="glassSolid"
              className="w-full"
              type="button"
              onClick={() => setIsLeaving(true)}
            >
              {t("auth.welcome.continueButton")}
              <ArrowRight className="size-4" />
            </Button>
          </motion.div>

          <motion.div className="flex w-full flex-col gap-3" {...riseIn(0.7)}>
            <LabeledDivider>{t("donate.title")}</LabeledDivider>

            <div className="flex w-full gap-2">
              <Pressable as="a" href={BOOSTY_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                <PiggyBank className="size-4" />
                {t("donate.boostyLabel")}
              </Pressable>
              <Pressable as="a" href={YOOKASSA_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                <Wallet className="size-4" />
                {t("donate.yookassaLabel")}
              </Pressable>
              <Pressable as="a" href={TELEGRAM_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                <TelegramIcon className="size-4" />
                {t("buildInfo.telegramButton")}
              </Pressable>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </DialogPortal>
  );
}
