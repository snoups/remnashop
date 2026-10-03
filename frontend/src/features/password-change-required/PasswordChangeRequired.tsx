import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { updateOwnProfile } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/Field";
import { PasswordInput } from "@shared/ui/PasswordInput";

export function PasswordChangeRequired() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="flex w-full max-w-sm flex-col gap-4 rounded-2xl border border-glass-border bg-surface/40 p-8 shadow-2xl backdrop-blur-xl"
      >
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-bold tracking-tight text-foreground">{t("auth.passwordChange.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("auth.passwordChange.description")}</p>
        </div>

        <Field label={t("auth.passwordChange.currentPasswordLabel")} htmlFor="force-current-password">
          <PasswordInput
            id="force-current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </Field>

        <Field label={t("profile.edit.newPasswordLabel")} htmlFor="force-new-password" info={t("auth.passwordHint")}>
          <PasswordInput
            id="force-new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("profile.edit.newPasswordPlaceholder")}
            required
          />
        </Field>

        <Field label={t("auth.confirmPassword")} htmlFor="force-confirm-password">
          <PasswordInput
            id="force-confirm-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("auth.confirmPasswordPlaceholder")}
            required
          />
        </Field>

        <Button variant="accent" type="submit" disabled={isSubmitting}>
          {t("auth.passwordChange.submit")}
        </Button>
      </form>
    </div>
  );
}
