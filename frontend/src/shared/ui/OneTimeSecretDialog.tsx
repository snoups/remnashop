import { AlertTriangle, KeyRound } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { DialogHeader } from "@shared/ui/DialogHeader";
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

  return (
    <>
      <DialogHeader icon={KeyRound} title={title} onClose={null} />

      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-start gap-2 rounded-xl border border-error/30 bg-error/10 px-3 py-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-error" />
          <p className="text-[12px] leading-snug text-error">{t("app.secretShownOnce")}</p>
        </div>
        <CopyableValue value={value} />
        <div className="flex justify-end">
          <Button variant="accent" type="button" onClick={close}>
            {t("app.done")}
          </Button>
        </div>
      </div>
    </>
  );
}
