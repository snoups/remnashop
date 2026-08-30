import { Check, Copy, KeyRound, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { DialogPortal } from "@shared/ui/DialogPortal";

interface RevealSecretDialogProps {
  secret: string;
  onDone: () => void;
}

export function RevealSecretDialog({ secret, onDone }: RevealSecretDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(secret);
    setCopied(true);
  };

  return (
    <DialogPortal>
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
      >
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
                <KeyRound className="size-4" />
              </div>
              {t("apiTokens.secretTitle")}
            </h2>
            <X className="size-4 text-muted-foreground" aria-hidden />
          </div>

          <div className="px-5 pt-4">
            <p className="text-[12.5px] font-medium text-error">{t("apiTokens.secretWarning")}</p>
            <code className="mt-3 block break-all rounded-xl border border-border bg-white/[0.04] p-3 text-[12.5px] text-foreground">
              {secret}
            </code>
          </div>

          <div className="flex gap-2 px-5 pb-5 pt-4">
            <motion.button
              type="button"
              onClick={() => void handleCopy()}
              {...bounceTap(bounceStrength)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? t("apiTokens.copied") : t("apiTokens.copy")}
            </motion.button>
            <motion.button
              type="button"
              onClick={onDone}
              {...bounceTap(bounceStrength)}
              className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
            >
              {t("apiTokens.done")}
            </motion.button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </DialogPortal>
  );
}
