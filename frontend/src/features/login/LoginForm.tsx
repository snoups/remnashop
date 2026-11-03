import { LogIn } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { login } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput } from "@shared/ui/glass/Input";

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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3">
      <Field label={t("auth.login")} htmlFor="login" required>
        <Input
          id="login"
          value={loginValue}
          onChange={(event) => setLoginValue(event.target.value)}
          autoComplete="username"
          placeholder={t("auth.loginPlaceholder")}
        />
      </Field>

      <Field label={t("auth.password")} htmlFor="password" required>
        <PasswordInput
          id="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          placeholder={t("auth.passwordPlaceholder")}
        />
      </Field>

      <Button variant="glassSolid" type="submit" icon={LogIn} isLoading={isSubmitting} className="mt-1">
        {t("auth.signIn")}
      </Button>
    </form>
  );
}
