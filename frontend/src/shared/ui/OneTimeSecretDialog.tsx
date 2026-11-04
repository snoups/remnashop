import { AlertTriangle, KeyRound } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { CopyInput } from "@shared/ui/glass/Input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

interface OneTimeSecretDialogProps {
  title: string;
  value: string;
  onDone: () => void;
}

/** A secret the backend returns once (API token, generated password). Only "Done" closes it, so it isn't lost by a stray click. */
export function OneTimeSecretDialog({ title, value, onDone }: OneTimeSecretDialogProps) {
  return (
    <Modal onClose={onDone} size="sm" dismissable={false}>
      <OneTimeSecretDialogBody title={title} value={value} />
    </Modal>
  );
}

function OneTimeSecretDialogBody({ title, value }: Omit<OneTimeSecretDialogProps, "onDone">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const id = useId();

  return (
    <>
      <DialogHeader icon={KeyRound} title={title} closable={false} />

      <div className="flex flex-col gap-3 p-3">
        <div className="flex items-start gap-2 rounded-xl bg-error/10 px-3.5 py-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-error" />
          <p className="text-[12px] leading-snug text-error">{t("app.secretShownOnce")}</p>
        </div>
        <CopyInput id={id} value={value} />
      </div>

      <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.08] p-4">
        <Button variant="glassAccent" onClick={close}>
          {t("app.done")}
        </Button>
      </div>
    </>
  );
}
