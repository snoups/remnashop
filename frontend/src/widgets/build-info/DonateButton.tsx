import { createPortal } from "react-dom";
import { Crown, Headset, MessageCircle, PiggyBank, Route, Users, Wallet } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { BOOSTY_URL, COMMUNITY_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { LABEL_CLASSNAME, MOBILE_NAV_ROW_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";
import { ModalCloseContext, useDialogFocus } from "@shared/ui/modal-hooks";
import {
  GLASS_DIALOG_CARD_CLASS,
  GLASS_DIALOG_CLASS,
  GLASS_DIALOG_PAD_CLASS,
  GLASS_LINK_BUTTON_CLASS,
  GLASS_SOLID_LINK_BUTTON_CLASS,
} from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

const PERKS = [
  { icon: Headset, key: "support" },
  { icon: Users, key: "community" },
  { icon: Route, key: "roadmap" },
  { icon: MessageCircle, key: "developer" },
] as const;

export function DonateButton({ mobile = false }: { mobile?: boolean }) {
  const renderOverlay = (content: ReactNode) => mobile ? createPortal(content, document.body) : content;
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);


  return (
    <>
      <Pressable
        type="button"
        onClick={() => setIsOpen(true)}
        className={mobile ? MOBILE_NAV_ROW_CLASSNAME : SIDEBAR_PILL_CLASSNAME}
      >
        <Crown className="size-4 shrink-0" />
        <span className={mobile ? "truncate" : LABEL_CLASSNAME}>{t("donate.button")}</span>
      </Pressable>

      {renderOverlay(<AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className={`fixed inset-0 ${mobile ? "z-60" : "z-40"} flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4`}
          >
            <button
              type="button"
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsOpen(false)}
            />

            <DonatePanel onEscape={() => setIsOpen(false)}>
              <DialogHeader icon={Crown} title={t("donate.title")} />

              <div className={`flex flex-col gap-3 ${GLASS_DIALOG_PAD_CLASS}`}>
                <div className={GLASS_DIALOG_CARD_CLASS}>
                  <p className="text-sm text-foreground">{t("donate.description")}</p>
                  <div className="flex gap-2">
                    <Pressable as="a" href={BOOSTY_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                      <PiggyBank className="size-4" />
                      {t("donate.boostyLabel")}
                    </Pressable>
                    <Pressable as="a" href={YOOKASSA_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                      <Wallet className="size-4" />
                      {t("donate.yookassaLabel")}
                    </Pressable>
                  </div>
                </div>

                <div className={GLASS_DIALOG_CARD_CLASS}>
                  <div>
                    <div className="text-sm font-medium text-foreground">{t("donate.communityTitle")}</div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{t("donate.communityDescription")}</p>
                  </div>
                  <ul className="flex flex-col gap-3">
                    {PERKS.map(({ icon, key }) => (
                      <li key={key} className="flex items-start gap-3">
                        <IconCircle icon={icon} />
                        <div>
                          <div className="text-sm text-foreground">{t(`donate.perks.${key}.title`)}</div>
                          <p className="text-xs text-muted-foreground">{t(`donate.perks.${key}.description`)}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <Pressable as="a" href={COMMUNITY_URL} target="_blank" rel="noreferrer" className={GLASS_SOLID_LINK_BUTTON_CLASS}>
                    {t("donate.communityButton")}
                  </Pressable>
                </div>
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
      <ModalCloseContext.Provider value={onEscape}>{children}</ModalCloseContext.Provider>
    </motion.div>
  );
}
