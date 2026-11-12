import { GitMerge, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { bindUserTelegram, listUsers, type UserBase } from "@entities/user/api";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

// the search also matches ids and names, so look past the first hit for the telegram_id owner
const OWNER_LOOKUP_LIMIT = 10;

interface BindTelegramDialogProps {
  user: UserBase;
  onBound: (user: UserBase) => void;
  /** the id is taken by `other`; the caller opens the merge with it */
  onMergeWith: (other: UserBase) => void;
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
  const [owner, setOwner] = useState<UserBase | null>(null);
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
      <DialogHeader icon={Send} title={t("users.telegram.action")} />
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col">
        <div className="p-4">
          <Field label={t("users.telegram.title")} htmlFor="user-telegram-id" error={error ?? undefined}>
            <Input
              id="user-telegram-id"
              inputMode="numeric"
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setError(null);
                setOwner(null);
              }}
              placeholder={t("users.telegram.idPlaceholder")}
              mono
              aria-invalid={error !== null}
            />
          </Field>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          {owner && (
            <Button
              variant="glass"
              type="button"
              // replaces this dialog in place; closing it first would clear the hand-off
              onClick={() => onMergeWith(owner)}
            >
              <GitMerge className="size-4" />
              {t("users.telegram.mergeWith", { id: owner.id })}
            </Button>
          )}
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={telegramId === null || error !== null} isLoading={isSubmitting}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
