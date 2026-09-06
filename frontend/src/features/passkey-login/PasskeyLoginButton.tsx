import { startAuthentication } from "@simplewebauthn/browser";
import { Fingerprint } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getPasskeyAuthenticationOptions, verifyPasskeyAuthentication } from "@entities/auth/passkeys";
import { getErrorMessage } from "@shared/api/http";
import { saveAccessToken } from "@shared/lib/token-storage";
import { toast } from "@shared/lib/toast";

interface PasskeyLoginButtonProps {
  onSuccess: () => void;
}

export function PasskeyLoginButton({ onSuccess }: PasskeyLoginButtonProps) {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    setIsLoading(true);
    try {
      const optionsJSON = await getPasskeyAuthenticationOptions();
      const response = await startAuthentication({ optionsJSON: optionsJSON as never });
      const result = await verifyPasskeyAuthentication(response as unknown as Record<string, unknown>);
      saveAccessToken(result.access_token);
      onSuccess();
    } catch (err) {
      if (err instanceof Error && err.name === "NotAllowedError") {
        toast.error(t("auth.oauth.passkeyCancelled"));
      } else if (err instanceof Error && err.name === "NotSupportedError") {
        toast.error(t("auth.oauth.passkeyNotSupported"));
      } else {
        toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      disabled={isLoading}
      className="flex w-full max-w-sm items-center justify-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Fingerprint size={16} />
      {t("auth.oauth.passkeySignIn")}
    </button>
  );
}
