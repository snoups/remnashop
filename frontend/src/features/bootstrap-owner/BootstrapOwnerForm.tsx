import { motion, type Variants } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { bootstrapOwner } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import { copyToClipboard } from "@shared/lib/clipboard";
import { LOGIN_PATTERN } from "@shared/lib/login-validation";
import { generatePassword, PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput } from "@shared/ui/glass/Input";

// fields dissolve one by one before the welcome screen takes over
const FORM_VARIANTS: Variants = {
  rest: {},
  leave: { transition: { staggerChildren: 0.04 } },
};
const FORM_ITEM_VARIANTS: Variants = {
  rest: { opacity: 1, y: 0, filter: "none" },
  leave: { opacity: 0, y: 10, filter: "blur(4px)", transition: { duration: 0.28, ease: "easeIn" } },
};

interface BootstrapOwnerFormProps {
  onSuccess: () => void;
}

export function BootstrapOwnerForm({ onSuccess }: BootstrapOwnerFormProps) {
  const { t } = useTranslation();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  const handleGeneratePassword = () => {
    const generated = generatePassword();
    setPassword(generated);
    setConfirmPassword(generated);

    // a refused copy is soft: the password is in both fields either way
    void copyToClipboard(generated).then((copied) => {
      if (!copied) return;
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const isLoginInvalid = login.trim() !== "" && !LOGIN_PATTERN.test(login.trim());

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (login.trim().length < 3) {
      toast.error(t("auth.errors.loginTooShort"));
      return;
    }

    if (!PASSWORD_PATTERN.test(password)) {
      toast.error(t("auth.errors.passwordRequirements"));
      return;
    }

    if (password !== confirmPassword) {
      toast.error(t("auth.errors.passwordsDoNotMatch"));
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await bootstrapOwner({ login, password });
      saveAccessToken(result.access_token);
      setIsLeaving(true);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      setIsSubmitting(false);
    }
  };

  return (
    <motion.form
      onSubmit={handleSubmit}
      className="flex w-full flex-col gap-3"
      variants={FORM_VARIANTS}
      initial={false}
      animate={isLeaving ? "leave" : "rest"}
      onAnimationComplete={(definition) => definition === "leave" && onSuccess()}
    >
      <motion.div variants={FORM_ITEM_VARIANTS} className="flex flex-col">
        <Field
          label={t("auth.login")}
          htmlFor="login"
          required
          error={isLoginInvalid ? t("auth.errors.loginInvalidChars") : undefined}
        >
          <Input
            id="login"
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            autoComplete="username"
            aria-invalid={isLoginInvalid}
            placeholder={t("auth.loginPlaceholder")}
          />
        </Field>
      </motion.div>

      <motion.div variants={FORM_ITEM_VARIANTS} className="flex flex-col">
        <Field label={t("auth.password")} htmlFor="password" info={t("auth.passwordHint")} required>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={24}
            // Safari's "Suggest Strong Password" reads this to generate a password
            // that already satisfies our rules (see PASSWORD_PATTERN above).
            passwordrules="minlength: 24; required: lower; required: upper; required: digit;"
            placeholder={t("auth.passwordPlaceholder")}
          />
        </Field>
      </motion.div>

      <motion.div variants={FORM_ITEM_VARIANTS} className="flex flex-col">
        <Field label={t("auth.confirmPassword")} htmlFor="confirm-password" required>
          <PasswordInput
            id="confirm-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("auth.confirmPasswordPlaceholder")}
          />
        </Field>
      </motion.div>

      <motion.div variants={FORM_ITEM_VARIANTS} className="flex flex-col">
        <Button
          variant="glass"
          type="button"
          onClick={handleGeneratePassword}
        >
          {copied ? t("auth.copiedToClipboard") : t("auth.generatePassword")}
        </Button>
      </motion.div>

      <motion.div variants={FORM_ITEM_VARIANTS} className="flex flex-col">
        <Button
          variant="glassSolid"
          type="submit"
          isLoading={isSubmitting}
          disabled={isLoginInvalid}
        >
          {t("auth.createOwnerAccount")}
        </Button>
      </motion.div>
    </motion.form>
  );
}
