import { LogIn } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { login } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";
import { Button } from "@shared/ui/Button";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { TextInput } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";

interface LoginFormProps {
  onSuccess: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { t } = useTranslation();
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      <Field label={t("auth.login")} htmlFor="login" aside={<span className="text-error">*</span>}>
        <TextInput
          id="login"
          value={loginValue}
          onChange={(event) => setLoginValue(event.target.value)}
          autoComplete="username"
          placeholder={t("auth.loginPlaceholder")}
        />
      </Field>

      <Field label={t("auth.password")} htmlFor="password" aside={<span className="text-error">*</span>}>
        <PasswordInput
          id="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          placeholder={t("auth.passwordPlaceholder")}
        />
      </Field>

      <Button
        variant="solid"
        type="submit"
        disabled={isSubmitting}
      >
        <LogIn size={16} />
        {t("auth.signIn")}
      </Button>
    </form>
  );
}
