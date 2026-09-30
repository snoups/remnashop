import { startAuthentication } from "@simplewebauthn/browser";
import { Fingerprint } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getPasskeyAuthenticationOptions, verifyPasskeyAuthentication } from "@entities/auth/passkeys";
import { getErrorMessage } from "@shared/api/http";
import { saveAccessToken } from "@shared/lib/token-storage";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";

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
    <Button
      variant="outline"
      className="w-full max-w-sm"
      type="button"
      onClick={() => void handleClick()}
      disabled={isLoading}
    >
      <Fingerprint size={16} />
      {t("auth.oauth.passkeySignIn")}
    </Button>
  );
}
