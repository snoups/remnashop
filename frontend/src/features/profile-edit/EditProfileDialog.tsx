import { KeyRound, Pencil } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { updateOwnProfile } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { copyToClipboard } from "@shared/lib/clipboard";
import { generatePassword, PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { initials } from "@shared/lib/initials";
import { useReloadCurrentUser } from "@entities/user/use-current-user";
import { Modal } from "@shared/ui/Modal";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";

interface EditProfileDialogProps {
  name: string;
  login: string | null;
}

export function EditProfileDialog({ name, login }: EditProfileDialogProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button variant="glass" icon={Pencil} onClick={() => setIsOpen(true)}>
        {t("common.edit")}
      </Button>

      {isOpen && (
        <Modal onClose={() => setIsOpen(false)} size="sm">
          <EditProfileDialogBody name={name} login={login} />
        </Modal>
      )}
    </>
  );
}

function EditProfileDialogBody({ name, login }: EditProfileDialogProps) {
  const { t } = useTranslation();
  const close = useModalClose();
  const reloadCurrentUser = useReloadCurrentUser();
  const [isPasswordOpen, setIsPasswordOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [nameValue, setNameValue] = useState(name);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [copied, setCopied] = useState(false);

  const handleGeneratePassword = () => {
    const generated = generatePassword();
    setNewPassword(generated);
    setConfirmPassword(generated);
    // a refused copy is soft: the password is in both fields either way
    void copyToClipboard(generated).then((ok) => {
      if (!ok) return;
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };


  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (newPassword && !currentPassword) {
      toast.error(t("profile.edit.currentPasswordRequired"));
      return;
    }

    if (newPassword && !PASSWORD_PATTERN.test(newPassword)) {
      toast.error(t("auth.errors.passwordRequirements"));
      return;
    }

    if (newPassword && newPassword !== confirmPassword) {
      toast.error(t("auth.errors.passwordsDoNotMatch"));
      return;
    }

    setIsSubmitting(true);
    try {
      await updateOwnProfile({
        name: nameValue !== name ? nameValue : undefined,
        current_password: newPassword ? currentPassword : undefined,
        new_password: newPassword || undefined,
      });
      reloadCurrentUser();
      toast.success(t("profile.edit.saved"));
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Pencil} title={t("profile.edit.title")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-3">
          <DialogCard variant="form">
            <div className="flex items-center gap-3">
              <div className="glass-control flex size-14 shrink-0 items-center justify-center rounded-full text-[18px] font-semibold text-foreground">
                {initials(login)}
              </div>
              <div className="min-w-0 flex-1">
                <Field label={t("profile.edit.nameLabel")} htmlFor="edit-name" required>
                  <Input id="edit-name" value={nameValue} maxLength={32} onChange={(event) => setNameValue(event.target.value)} />
                </Field>
              </div>
            </div>
          </DialogCard>

          <DialogCard>
            <Row
              icon={KeyRound}
              label={t("profile.edit.changePassword")}
              expanded={isPasswordOpen}
              onClick={() => setIsPasswordOpen((open) => !open)}
              panel={
                <>
                  <Field label={t("profile.edit.currentPasswordLabel")} htmlFor="edit-current-password" required>
                    <PasswordInput
                      id="edit-current-password"
                      value={currentPassword}
                      onChange={(event) => setCurrentPassword(event.target.value)}
                      autoComplete="current-password"
                      placeholder={t("profile.edit.currentPasswordPlaceholder")}
                    />
                  </Field>

                  <Field label={t("profile.edit.newPasswordLabel")} htmlFor="edit-new-password" required info={t("auth.passwordHint")}>
                    <PasswordInput
                      id="edit-new-password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      autoComplete="new-password"
                      minLength={24}
                      // Safari's "Suggest Strong Password" reads this to generate a password that passes PASSWORD_PATTERN
                      passwordrules="minlength: 24; required: lower; required: upper; required: digit;"
                      placeholder={t("profile.edit.newPasswordPlaceholder")}
                    />
                  </Field>

                  <Field label={t("auth.confirmPassword")} htmlFor="edit-confirm-password" required>
                    <PasswordInput
                      id="edit-confirm-password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      autoComplete="new-password"
                      placeholder={t("auth.confirmPasswordPlaceholder")}
                    />
                  </Field>

                  <Button variant="glass" type="button" onClick={handleGeneratePassword}>
                    {copied ? t("auth.copiedToClipboard") : t("auth.generatePassword")}
                  </Button>
                </>
              }
            />
          </DialogCard>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("common.saving") : t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
