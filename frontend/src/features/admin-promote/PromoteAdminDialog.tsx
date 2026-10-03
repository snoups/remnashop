import { ShieldPlus } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { promoteAdmin } from "@entities/admin/api";
import type { UserListItem } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { LOGIN_PATTERN } from "@shared/lib/login-validation";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Field } from "@shared/ui/Field";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { OneTimeSecretDialog } from "@shared/ui/OneTimeSecretDialog";
import { TextInput } from "@shared/ui/TextInput";

interface PromoteAdminDialogProps {
  user: Pick<UserListItem, "id" | "name" | "login">;
  /** The promotion went through; `login` is the one the new admin signs in with. */
  onPromoted: (login: string) => void;
  /** Fires once everything is closed, cancelled or done. */
  onClose: () => void;
}

/** Confirm (plus a login when the user has none), then reveal a generated password once. */
export function PromoteAdminDialog({ user, onPromoted, onClose }: PromoteAdminDialogProps) {
  const { t } = useTranslation();
  const passwordRef = useRef<string | null>(null);
  const [password, setPassword] = useState<string | null>(null);

  if (password) {
    return <OneTimeSecretDialog title={t("admins.passwordModal.title")} value={password} onDone={onClose} />;
  }

  return (
    <Modal onClose={() => (passwordRef.current ? setPassword(passwordRef.current) : onClose())} size="sm">
      <PromoteAdminForm
        user={user}
        onPromoted={(login, generated) => {
          passwordRef.current = generated;
          onPromoted(login);
        }}
      />
    </Modal>
  );
}

function PromoteAdminForm({
  user,
  onPromoted,
}: {
  user: PromoteAdminDialogProps["user"];
  onPromoted: (login: string, password: string | null) => void;
}) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [login, setLogin] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const needsLogin = user.login === null;
  const isLoginInvalid = login.trim() !== "" && !LOGIN_PATTERN.test(login.trim());

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const result = await promoteAdmin({
        user_id: user.id,
        login: needsLogin ? login.trim() : undefined,
        permission_grants: [],
        permission_revokes: [],
      });
      if (!result.password) toast.success(t("admins.promote.success", { name: user.name }));
      onPromoted(result.admin.login ?? login.trim(), result.password);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.promote.error")));
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={ShieldPlus} title={t("admins.promote.title")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-4">
          <p className="text-[13px] text-foreground/80">{t("admins.promote.message", { name: user.name })}</p>
          {needsLogin && (
            <Card variant="form">
              <Field
                label={t("admins.promote.loginLabel")}
                htmlFor="admin-promote-login"
                hint={t("admins.promote.loginHint")}
                required
                error={isLoginInvalid ? t("auth.errors.loginInvalidChars") : undefined}
              >
                <TextInput
                  id="admin-promote-login"
                  value={login}
                  onChange={(event) => setLogin(event.target.value)}
                  placeholder={t("admins.promote.loginLabel")}
                  required
                  aria-invalid={isLoginInvalid}
                />
              </Field>
            </Card>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={close}>
              {t("common.cancel")}
            </Button>
            <Button variant="accent" type="submit" disabled={isSubmitting || isLoginInvalid}>
              {t("admins.promote.submit")}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
