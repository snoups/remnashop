import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { updateOwnProfile } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { copyToClipboard } from "@shared/lib/clipboard";
import { generatePassword, PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { Button } from "@shared/ui/Button";
import { GLASS_STANDALONE_CARD_CLASS, SCREEN_TITLE_CLASS } from "@shared/ui/classes";
import { Field } from "@shared/ui/glass/Field";
import { PasswordInput } from "@shared/ui/glass/Input";

export function PasswordChangeRequired() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
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

    if (!PASSWORD_PATTERN.test(newPassword)) {
      toast.error(t("auth.errors.passwordRequirements"));
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error(t("auth.errors.passwordsDoNotMatch"));
      return;
    }

    setIsSubmitting(true);
    try {
      await updateOwnProfile({ current_password: currentPassword, new_password: newPassword });
      // a password change revokes every session, this one included
      clearAccessToken();
      toast.success(t("auth.passwordChange.done"));
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      setIsSubmitting(false);
    }
  };

  // the sign-in page's card: the same glass, fields and actions
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className={`flex w-full max-w-sm flex-col gap-3 ${GLASS_STANDALONE_CARD_CLASS}`}
      >
        <div className="mb-3 flex flex-col gap-2">
          <h1 className={SCREEN_TITLE_CLASS}>{t("auth.passwordChange.title")}</h1>
          <p className="text-[13px] text-muted-foreground">{t("auth.passwordChange.description")}</p>
        </div>

        <Field label={t("auth.passwordChange.currentPasswordLabel")} htmlFor="force-current-password" required>
          <PasswordInput
            id="force-current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
          />
        </Field>

        <Field label={t("profile.edit.newPasswordLabel")} htmlFor="force-new-password" info={t("auth.passwordHint")} required>
          <PasswordInput
            id="force-new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("profile.edit.newPasswordPlaceholder")}
          />
        </Field>

        <Field label={t("auth.confirmPassword")} htmlFor="force-confirm-password" required>
          <PasswordInput
            id="force-confirm-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("auth.confirmPasswordPlaceholder")}
          />
        </Field>

        <Button variant="glass" type="button" onClick={handleGeneratePassword}>
          {copied ? t("auth.copiedToClipboard") : t("auth.generatePassword")}
        </Button>

        <Button variant="glassSolid" type="submit" isLoading={isSubmitting}>
          {t("auth.passwordChange.submit")}
        </Button>
      </form>
    </div>
  );
}
