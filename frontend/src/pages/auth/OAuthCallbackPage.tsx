import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { getErrorMessage } from "@shared/api/http";
import { oauthConnectCallback, oauthLoginCallback, type OAuthProvider } from "@entities/auth/oauth";
import { BrandMark } from "@entities/appearance/BrandMark";
import { useBrandName } from "@entities/appearance/use-appearance";
import { consumeOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { saveAccessToken } from "@shared/lib/token-storage";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { GLASS_STANDALONE_CARD_CLASS } from "@shared/ui/classes";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

function isOAuthProvider(value: string | undefined): value is OAuthProvider {
  return value === "github" || value === "telegram" || value === "oidc";
}

export function OAuthCallbackPage() {
  const { t } = useTranslation();
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const ranRef = useRef(false);
  const brandName = useBrandName();

  useDocumentTitle(brandName, t("auth.loginPageTitle"));

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const flow = consumeOAuthFlow();

    if (!isOAuthProvider(provider) || !code || !state || !flow) {
      toast.error(t("auth.oauth.invalidCallback"));
      navigate("/", { replace: true });
      return;
    }

    const run = async () => {
      try {
        if (flow.purpose === "login") {
          const result = await oauthLoginCallback(provider, { code, state });
          saveAccessToken(result.access_token);
          navigate("/dashboard", { replace: true });
        } else {
          await oauthConnectCallback(provider, { code, state });
          navigate("/dashboard/profile", { replace: true });
        }
      } catch (err) {
        toast.error(getErrorMessage(err, t("common.errors.generic")));
        navigate("/", { replace: true });
      }
    };

    void run();
  }, [provider, searchParams, navigate, t]);

  return <OAuthCallbackScreen />;
}

/** The wait while the provider's answer is exchanged; also shown on /dashboard/debug. */
export function OAuthCallbackScreen() {
  const { t } = useTranslation();
  const brandName = useBrandName();

  return (
    // the sign-in page's brand and card, holding the wait
    <div className="relative flex min-h-screen flex-col items-center justify-center px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <div className="flex w-full max-w-sm flex-col items-center gap-6">
        <div className="flex items-center gap-3">
          <BrandMark className="size-9 shrink-0 text-primary" />
          <h1 className="text-[21px] font-bold tracking-tight text-foreground">{brandName}</h1>
        </div>
        <div className={`flex w-full flex-col items-center gap-3 text-center ${GLASS_STANDALONE_CARD_CLASS}`}>
          <Loader2 className="size-6 animate-spin text-primary" />
          <p className="text-[13px] text-muted-foreground">{t("auth.oauth.completingSignIn")}</p>
        </div>
      </div>
    </div>
  );
}
