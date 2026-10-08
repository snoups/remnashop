import { GitMerge, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { bindUserTelegram, listUsers, type UserListItem } from "@entities/user/api";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Field } from "@shared/ui/Field";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { TextInput } from "@shared/ui/TextInput";

// the search also matches ids and names, so look past the first hit for the telegram_id owner
const OWNER_LOOKUP_LIMIT = 10;

interface BindTelegramDialogProps {
  user: UserListItem;
  onBound: (user: UserListItem) => void;
  /** the id is taken by `other`; the caller opens the merge with it */
  onMergeWith: (other: UserListItem) => void;
  onClose: () => void;
}

export function BindTelegramDialog({ onClose, ...props }: BindTelegramDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <BindTelegramForm {...props} />
    </Modal>
  );
}

function BindTelegramForm({ user, onBound, onMergeWith }: Omit<BindTelegramDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [value, setValue] = useState(user.telegram_id === null ? "" : String(user.telegram_id));
  const [error, setError] = useState<string | null>(null);
  const [owner, setOwner] = useState<UserListItem | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const telegramId = /^\d+$/.test(value.trim()) ? Number(value.trim()) : null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (telegramId === null) return;
    setIsSubmitting(true);
    try {
      onBound(await bindUserTelegram(user.id, telegramId));
      toast.success(t("users.telegram.done"));
      close();
    } catch (err) {
      if (err instanceof ApiError && err.code === "TELEGRAM_ID_TAKEN") {
        setError(t("users.telegram.taken"));
        const found = await listUsers({
          search: String(telegramId),
          pageSize: OWNER_LOOKUP_LIMIT,
          includeStaff: true,
          deleted: "exclude",
        }).catch(() => null);
        setOwner(found?.items.find((u) => u.telegram_id === telegramId) ?? null);
      } else if (err instanceof ApiError && err.code === "TELEGRAM_ID_BLACKLISTED") {
        setError(getErrorMessage(err, t("users.telegram.error")));
      } else {
        toast.error(getErrorMessage(err, t("users.telegram.error")));
      }
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Send} title={t("users.telegram.title")} />
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-3 p-4">
        <Card variant="form">
          <Field label={t("users.telegram.title")} htmlFor="user-telegram-id" error={error ?? undefined}>
            <TextInput
              id="user-telegram-id"
              inputMode="numeric"
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setError(null);
                setOwner(null);
              }}
              placeholder="123456789"
              className="font-mono"
              aria-invalid={error !== null}
            />
          </Field>
        </Card>
        <div className="flex justify-end gap-2">
          {owner && (
            <Button
              variant="secondary"
              type="button"
              // replaces this dialog in place; closing it first would clear the hand-off
              onClick={() => onMergeWith(owner)}
            >
              <GitMerge className="size-3.5" />
              {t("users.telegram.mergeWith", { id: owner.id })}
            </Button>
          )}
          <Button variant="outline" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="accent" type="submit" disabled={isSubmitting || telegramId === null || error !== null}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
