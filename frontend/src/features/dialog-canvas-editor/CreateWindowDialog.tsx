import { Loader2, MessagesSquare } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Field } from "@shared/ui/Field";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { TextInput } from "@shared/ui/TextInput";

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
    if (!trimmed) return;
    setIsSubmitting(true);
    const created = await onCreate(trimmed);
    setIsSubmitting(false);
    if (created) close();
  };

  return (
    <>
      <DialogHeader icon={MessagesSquare} title={t("dialogs.windowList.addWindowTitle")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-4">
          <Card variant="form">
            <Field
              label={t("dialogs.windowList.addWindowNameLabel")}
              htmlFor="create-window-name"
              required
              hint={t("dialogs.windowList.addWindowNameHint")}
            >
              <TextInput
                id="create-window-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t("dialogs.windowList.addWindowTitlePlaceholder")}
                maxLength={WINDOW_NAME_MAX_LENGTH}
                autoFocus
                required
              />
            </Field>
          </Card>
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={close}>
              {t("common.cancel")}
            </Button>
            <Button variant="accent" type="submit" disabled={isSubmitting || !trimmed}>
              {isSubmitting && <Loader2 className="size-3.5 animate-spin" />}
              {t("common.create")}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
