import { Check, Copy, KeyRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { DialogPortal } from "@shared/ui/DialogPortal";

interface AdminPasswordModalProps {
  password: string;
  onClose: () => void;
}

export function AdminPasswordModal({ password, onClose }: AdminPasswordModalProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(password).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  return (
    <DialogPortal>
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
        >
          <div className="border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                <KeyRound className="size-4" />
              </div>
              {t("admins.passwordModal.title")}
            </h2>
            <p className="mt-1 text-[12.5px] text-muted-foreground">{t("admins.passwordModal.description")}</p>
          </div>

          <div className="px-5 py-4">
            <button
              type="button"
              onClick={handleCopy}
              className={`flex w-full items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-left font-mono text-sm text-foreground transition-colors ${
                isCopied ? "border-success/40 bg-success/10" : "border-border bg-input/60 hover:bg-white/[0.06]"
              }`}
            >
              <span className="select-all truncate">{password}</span>
              {isCopied ? (
                <Check className="size-4 shrink-0 text-success" />
              ) : (
                <Copy className="size-4 shrink-0 text-muted-foreground" />
              )}
            </button>
          </div>

          <div className="px-5 pb-5">
            <motion.button
              type="button"
              onClick={onClose}
              {...bounceTap(bounceStrength)}
              className="w-full rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
            >
              {t("admins.passwordModal.close")}
            </motion.button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </DialogPortal>
  );
}
