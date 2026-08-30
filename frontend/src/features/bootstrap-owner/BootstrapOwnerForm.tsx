import { Eye, EyeOff } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { bootstrapOwner } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";
import { FieldHint } from "@shared/ui/FieldHint";

import { WelcomeDonateDialog } from "./WelcomeDonateDialog";

const PASSWORD_CHARSET =
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const GENERATED_PASSWORD_LENGTH = 32;

function generatePassword(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(GENERATED_PASSWORD_LENGTH));
  return Array.from(bytes, (byte) => PASSWORD_CHARSET[byte % PASSWORD_CHARSET.length]).join("");
}

interface BootstrapOwnerFormProps {
  onSuccess: () => void;
}

export function BootstrapOwnerForm({ onSuccess }: BootstrapOwnerFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [justBootstrapped, setJustBootstrapped] = useState(false);

  const handleGeneratePassword = () => {
    const generated = generatePassword();
    setPassword(generated);
    setConfirmPassword(generated);

    navigator.clipboard
      .writeText(generated)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {
        // Clipboard access can be denied by the browser; the password is still
        // filled into both fields, so this is a soft failure.
      });
  };

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
      setJustBootstrapped(true);
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (justBootstrapped) {
    return <WelcomeDonateDialog onContinue={onSuccess} />;
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="login" className="text-sm font-medium text-foreground/80">
          {t("auth.login")} <span className="text-error">*</span>
        </label>
        <input
          id="login"
          value={login}
          onChange={(event) => setLogin(event.target.value)}
          autoComplete="username"
          pattern="[A-Za-z0-9._-]+"
          title={t("auth.errors.loginInvalidChars")}
          placeholder={t("auth.loginPlaceholder")}
          className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="password" className="flex items-center gap-1.5 text-sm font-medium text-foreground/80">
          {t("auth.password")} <span className="text-error">*</span>
          <FieldHint text={t("auth.passwordHint")} />
        </label>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={24}
            // Safari's "Suggest Strong Password" reads this to generate a password
            // that already satisfies our rules (see PASSWORD_PATTERN above).
            passwordrules="minlength: 24; required: lower; required: upper; required: digit;"
            placeholder={t("auth.passwordPlaceholder")}
            className="w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-10 text-sm text-foreground outline-none focus:border-primary"
          />
          <motion.button
            type="button"
            onClick={() => setShowPassword((value) => !value)}
            tabIndex={-1}
            {...bounceTap(bounceStrength, 0.12)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </motion.button>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="confirm-password" className="text-sm font-medium text-foreground/80">
          {t("auth.confirmPassword")} <span className="text-error">*</span>
        </label>
        <div className="relative">
          <input
            id="confirm-password"
            type={showConfirmPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={t("auth.confirmPasswordPlaceholder")}
            className="w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-10 text-sm text-foreground outline-none focus:border-primary"
          />
          <motion.button
            type="button"
            onClick={() => setShowConfirmPassword((value) => !value)}
            tabIndex={-1}
            {...bounceTap(bounceStrength, 0.12)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
          >
            {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </motion.button>
        </div>
      </div>

      <button
        type="button"
        onClick={handleGeneratePassword}
        className="rounded-full border border-border px-4 py-2 font-medium text-foreground/80 transition hover:bg-white/5 hover:text-foreground active:scale-95"
      >
        {copied ? t("auth.copiedToClipboard") : t("auth.generatePassword")}
      </button>

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-full bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:bg-primary-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {t("auth.createOwnerAccount")}
      </button>
    </form>
  );
}
