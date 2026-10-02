import { ChevronDown, Eye, EyeOff, Pencil } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { updateOwnProfile } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { useReloadCurrentUser } from "@entities/user/use-current-user";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { TextInput } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";
import { Card } from "@shared/ui/Card";

interface EditProfileDialogProps {
  name: string;
  login: string | null;
}

export function EditProfileDialog({ name, login }: EditProfileDialogProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button
        variant="secondary"
        onClick={() => setIsOpen(true)}
      >
        <Pencil className="size-3.5" />
        {t("profile.edit.button")}
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
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const initials = (login ?? "?").slice(0, 2).toUpperCase();

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
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Pencil} title={t("profile.edit.title")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        {/* small form, nothing scrolls: the buttons sit under the fields, no footer */}
        <div className="flex flex-col gap-3 p-4">
          <Card variant="form">
            <div className="flex size-14 items-center justify-center rounded-full bg-foreground text-[18px] font-bold text-canvas">
              {initials}
            </div>

            <Field label={t("profile.edit.nameLabel")} htmlFor="edit-name">
              <TextInput
                id="edit-name"
                value={nameValue}
                maxLength={32}
                onChange={(event) => setNameValue(event.target.value)}
              />
            </Field>

            <div>
              <motion.button
                type="button"
                onClick={() => setIsPasswordOpen((open) => !open)}
                {...bounceTap()}
                className="flex w-full items-center justify-between rounded-xl py-1 text-sm font-medium text-foreground/80 transition-colors hover:text-foreground"
              >
                {t("profile.edit.changePassword")}
                <ChevronDown
                  className={`size-4 text-muted-foreground transition-transform ${isPasswordOpen ? "rotate-180" : ""}`}
                />
              </motion.button>

              <AnimatePresence initial={false}>
                {isPasswordOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                    className="overflow-hidden"
                  >
                    <div className="flex flex-col gap-4 pt-3">
                      <Field label={t("profile.edit.currentPasswordLabel")} htmlFor="edit-current-password">
                        <div className="relative">
                          <TextInput
                            id="edit-current-password"
                            type={showCurrentPassword ? "text" : "password"}
                            value={currentPassword}
                            onChange={(event) => setCurrentPassword(event.target.value)}
                            autoComplete="current-password"
                            placeholder={t("profile.edit.currentPasswordPlaceholder")}
                            className="w-full pr-10"
                          />
                          <motion.button
                            type="button"
                            onClick={() => setShowCurrentPassword((value) => !value)}
                            tabIndex={-1}
                            {...bounceTap(0.12)}
                            className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                          >
                            {showCurrentPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                          </motion.button>
                        </div>
                      </Field>

                      <Field label={t("profile.edit.newPasswordLabel")} htmlFor="edit-new-password" info={t("auth.passwordHint")}>
                        <div className="relative">
                          <TextInput
                            id="edit-new-password"
                            type={showNewPassword ? "text" : "password"}
                            value={newPassword}
                            onChange={(event) => setNewPassword(event.target.value)}
                            autoComplete="new-password"
                            placeholder={t("profile.edit.newPasswordPlaceholder")}
                            className="w-full pr-10"
                          />
                          <motion.button
                            type="button"
                            onClick={() => setShowNewPassword((value) => !value)}
                            tabIndex={-1}
                            {...bounceTap(0.12)}
                            className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                          >
                            {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                          </motion.button>
                        </div>
                      </Field>

                      <Field label={t("auth.confirmPassword")} htmlFor="edit-confirm-password">
                        <div className="relative">
                          <TextInput
                            id="edit-confirm-password"
                            type={showConfirmPassword ? "text" : "password"}
                            value={confirmPassword}
                            onChange={(event) => setConfirmPassword(event.target.value)}
                            autoComplete="new-password"
                            placeholder={t("auth.confirmPasswordPlaceholder")}
                            className="w-full pr-10"
                          />
                          <motion.button
                            type="button"
                            onClick={() => setShowConfirmPassword((value) => !value)}
                            tabIndex={-1}
                            {...bounceTap(0.12)}
                            className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                          >
                            {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                          </motion.button>
                        </div>
                      </Field>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </Card>
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={close}>
              {t("profile.edit.cancel")}
            </Button>
            <Button variant="accent" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("profile.edit.saving") : t("profile.edit.save")}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
