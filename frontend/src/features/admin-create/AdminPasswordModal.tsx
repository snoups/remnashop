import { Check, Copy, KeyRound } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface AdminPasswordModalProps {
  password: string;
  onClose: () => void;
}

export function AdminPasswordModal({ password, onClose }: AdminPasswordModalProps) {
  return (
    <Modal onClose={onClose} size="sm" dismissable={false}>
      <AdminPasswordModalBody password={password} />
    </Modal>
  );
}

function AdminPasswordModalBody({ password }: { password: string }) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard?.writeText(password).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  return (
    <>
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
          className="relative flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-input/60 px-3 py-2.5 text-left font-mono text-sm text-foreground transition-colors hover:bg-white/[0.06]"
        >
          <span className={`contents ${isCopied ? "[&>*]:opacity-0" : ""}`}>
            <span className="select-all truncate">{password}</span>
            <Copy className="size-4 shrink-0 text-muted-foreground" />
          </span>
          {isCopied && (
            <span className="absolute inset-0 flex items-center justify-center gap-1.5 font-sans text-[12.5px] font-medium text-success">
              <Check className="size-3.5" />
              {t("app.copied")}
            </span>
          )}
        </button>
      </div>

      <div className="px-5 pb-5">
        <motion.button
          type="button"
          onClick={close}
          {...bounceTap(bounceStrength)}
          className="w-full rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
        >
          {t("admins.passwordModal.close")}
        </motion.button>
      </div>
    </>
  );
}
