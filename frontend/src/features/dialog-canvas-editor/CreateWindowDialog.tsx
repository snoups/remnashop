import { MessagesSquare } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

// the backend's CreateCustomWindowRequest.name limit
const WINDOW_NAME_MAX_LENGTH = 128;

interface CreateWindowDialogProps {
  /** resolves true once the window exists; false keeps the dialog open with the typed name */
  onCreate: (name: string) => Promise<boolean>;
  onClose: () => void;
}

export function CreateWindowDialog({ onCreate, onClose }: CreateWindowDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <CreateWindowDialogBody onCreate={onCreate} />
    </Modal>
  );
}

function CreateWindowDialogBody({ onCreate }: Pick<CreateWindowDialogProps, "onCreate">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const trimmed = name.trim();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    const created = await onCreate(trimmed);
    setIsSubmitting(false);
    if (created) close();
  };

  return (
    <>
      <DialogHeader icon={MessagesSquare} title={t("dialogs.windowList.addWindowTitle")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="p-4">
          <Field
            label={t("dialogs.windowList.addWindowNameLabel")}
            htmlFor="create-window-name"
            required
            hint={t("dialogs.windowList.addWindowNameHint")}
          >
            <Input
              id="create-window-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("dialogs.windowList.addWindowTitlePlaceholder")}
              maxLength={WINDOW_NAME_MAX_LENGTH}
              autoFocus
            />
          </Field>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isSubmitting}>
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
