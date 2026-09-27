import { Check, Copy, KeyRound, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface RevealSecretDialogProps {
  secret: string;
  onDone: () => void;
}

export function RevealSecretDialog({ secret, onDone }: RevealSecretDialogProps) {
  return (
    <Modal onClose={onDone} size="lg" dismissable={false}>
      <RevealSecretDialogBody secret={secret} />
    </Modal>
  );
}

function RevealSecretDialogBody({ secret }: { secret: string }) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard
      ?.writeText(secret)
      .then(() => setCopied(true))
      .catch(() => {});
  };

  return (
    <>
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
        <code className="mt-3 block overflow-x-auto whitespace-nowrap rounded-xl border border-border bg-white/[0.04] p-3 text-[12.5px] text-foreground">
          {secret}
        </code>
      </div>

      <div className="flex gap-2 px-5 pb-5 pt-4">
        <motion.button
          type="button"
          onClick={handleCopy}
          {...bounceTap(bounceStrength)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? t("apiTokens.copied") : t("apiTokens.copy")}
        </motion.button>
        <motion.button
          type="button"
          onClick={close}
          {...bounceTap(bounceStrength)}
          className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
        >
          {t("apiTokens.done")}
        </motion.button>
      </div>
    </>
  );
}
