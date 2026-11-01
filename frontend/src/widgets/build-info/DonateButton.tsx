import { createPortal } from "react-dom";
import { Crown, PiggyBank, Wallet } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { BOOSTY_URL, COMMUNITY_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";
import { Card } from "@shared/ui/Card";
import { useDialogFocus } from "@shared/ui/modal-hooks";
import { GLASS_DIALOG_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

export function DonateButton({ mobile = false }: { mobile?: boolean }) {
  const renderOverlay = (content: ReactNode) => mobile ? createPortal(content, document.body) : content;
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);


  return (
    <>
      <Pressable
        type="button"
        aria-label={t("donate.button")}
        onClick={() => setIsOpen(true)}
        className={mobile ? "flex size-11 shrink-0 items-center justify-center gap-1.5 rounded-full border border-glass-border bg-white/[0.05] px-2 text-[12.5px] font-semibold text-muted-foreground hover:bg-white/[0.07] hover:text-foreground" : SIDEBAR_PILL_CLASSNAME}
      >
        {mobile ? <Crown className="size-5" /> : <Crown className="size-4 shrink-0" />}
        {!mobile && <span className={LABEL_CLASSNAME}>{t("donate.button")}</span>}
      </Pressable>

      {renderOverlay(<AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className={`fixed inset-0 ${mobile ? "z-[60]" : "z-40"} flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4`}
          >
            <button
              type="button"
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsOpen(false)}
            />

            <DonatePanel onEscape={() => setIsOpen(false)}>
              <DialogHeader icon={Crown} title={t("donate.title")} onClose={() => setIsOpen(false)} />

              <div className="flex flex-col gap-3 px-5 pb-5 pt-4">
                <p className="text-[12.5px] text-foreground">{t("donate.description")}</p>

                <div className="flex gap-2">
                  <Pressable as="a"
                    href={BOOSTY_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border h-9 px-3 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                  >
                    <PiggyBank className="size-4" />
                    {t("donate.boostyLabel")}
                  </Pressable>
                  <Pressable as="a"
                    href={YOOKASSA_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border h-9 px-3 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                  >
                    <Wallet className="size-4" />
                    {t("donate.yookassaLabel")}
                  </Pressable>
                </div>

                <Card>
                  <div className="text-[13px] font-semibold text-foreground">{t("donate.communityTitle")}</div>
                  <p className="mt-1 text-[12.5px] text-muted-foreground">{t("donate.communityDescription")}</p>
                  <Pressable as="a"
                    href={COMMUNITY_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 flex items-center justify-center gap-2 rounded-full border border-transparent bg-accent h-9 px-3 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    {t("donate.communityButton")}
                  </Pressable>
                </Card>
              </div>
            </DonatePanel>
          </motion.div>
        )}
      </AnimatePresence>)}
    </>
  );
}

// Own overlay and animation on purpose (like BuildInfoBadge), with Modal's keyboard and a11y behaviour:
// mounted only while open, so useDialogFocus runs on open and restores focus on close.
function DonatePanel({ onEscape, children }: { onEscape: () => void; children: ReactNode }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogFocus(panelRef, onEscape);

  return (
    <motion.div
      ref={panelRef}
      data-dialog
      tabIndex={-1}
      initial={{ opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.94, y: 8 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className={`relative z-50 w-full max-w-sm outline-none ${GLASS_DIALOG_CLASS}`}
    >
      {children}
    </motion.div>
  );
}
