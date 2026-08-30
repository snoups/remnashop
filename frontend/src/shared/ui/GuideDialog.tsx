import { CircleHelp, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { DialogPortal } from "@shared/ui/DialogPortal";

interface GuideDialogProps {
  ariaLabel: string;
  title: string;
  children: ReactNode;
}

export function GuideDialog({ ariaLabel, title, children }: GuideDialogProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen(true);
        }}
        aria-label={ariaLabel}
        className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
      >
        <CircleHelp className="size-4" />
      </button>

      <DialogPortal>
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
              onClick={(event) => event.stopPropagation()}
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
                className="relative z-50 flex max-h-[85vh] w-full max-w-lg flex-col rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
              >
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                      <CircleHelp className="size-4" />
                    </div>
                    {title}
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

                <div className="flex flex-col gap-5 overflow-y-auto px-5 py-4 text-sm text-foreground/90">
                  {children}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </DialogPortal>
    </>
  );
}
