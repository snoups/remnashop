import { Crown, PiggyBank, Wallet, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BOOSTY_URL, COMMUNITY_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";

export function DonateButton() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);

  const tapProps = bounceTap(bounceStrength, 0.12);

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label={t("donate.button")}
        title={t("donate.button")}
        className={SIDEBAR_PILL_CLASSNAME}
        initial="rest"
        whileHover="hover"
        {...bounceTap(bounceStrength)}
      >
        <BounceIcon icon={Crown} size={17} hoverSize={23.5} />
        <span className={LABEL_CLASSNAME}>{t("donate.button")}</span>
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
          >
            <button
              type="button"
              aria-hidden
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
            >
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                    <Crown className="size-4" />
                  </div>
                  {t("donate.title")}
                </h2>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  aria-label={t("profile.edit.close")}
                  className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>

              <div className="flex flex-col gap-3 px-5 pb-5 pt-4">
                <p className="text-[12.5px] text-muted-foreground">{t("donate.description")}</p>

                <div className="flex gap-2">
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
                </div>

                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                  <div className="text-[13px] font-semibold text-foreground">{t("donate.communityTitle")}</div>
                  <p className="mt-1 text-[12.5px] text-muted-foreground">{t("donate.communityDescription")}</p>
                  <motion.a
                    href={COMMUNITY_URL}
                    target="_blank"
                    rel="noreferrer"
                    {...tapProps}
                    className="mt-3 flex items-center justify-center gap-2 rounded-full bg-accent px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    {t("donate.communityButton")}
                  </motion.a>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
