import { Eye, EyeOff, LogIn } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { login } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";

interface LoginFormProps {
  onSuccess: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await login({ login: loginValue, password });
      saveAccessToken(result.access_token);
      onSuccess();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="login" className="text-sm font-medium text-foreground/80">
          {t("auth.login")} <span className="text-error">*</span>
        </label>
        <input
          id="login"
          value={loginValue}
          onChange={(event) => setLoginValue(event.target.value)}
          autoComplete="username"
          placeholder={t("auth.loginPlaceholder")}
          className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="password" className="text-sm font-medium text-foreground/80">
          {t("auth.password")} <span className="text-error">*</span>
        </label>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
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

      <motion.button
        type="submit"
        disabled={isSubmitting}
        {...bounceTap(bounceStrength)}
        className="flex items-center justify-center gap-2 rounded-full bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        <LogIn size={16} />
        {t("auth.signIn")}
      </motion.button>
    </form>
  );
}
