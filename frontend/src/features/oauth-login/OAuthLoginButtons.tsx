import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { getOAuthLoginAuthorizeUrl, type OAuthProvider } from "@entities/auth/oauth";
import { isHttpsUrl } from "@shared/lib/external-links";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";

const PROVIDERS: OAuthProvider[] = ["github", "telegram", "oidc"];

interface OAuthLoginButtonsProps {
  oauthProviders: Record<string, boolean>;
  oidcDisplayName: string | null;
}

export function OAuthLoginButtons({ oauthProviders, oidcDisplayName }: OAuthLoginButtonsProps) {
  const { t } = useTranslation();
  // stays set on success: the page is about to navigate away to the provider
  const [pending, setPending] = useState<OAuthProvider | null>(null);

  const providerLabels: Record<OAuthProvider, string> = {
    github: t("profile.oauthAccounts.github"),
    telegram: t("profile.oauthAccounts.telegram"),
    oidc: oidcDisplayName || t("profile.oauthAccounts.oidcFallback"),
  };

  const enabled = PROVIDERS.filter((provider) => oauthProviders[provider]);

  if (enabled.length === 0) return null;

  const handleClick = async (provider: OAuthProvider) => {
    setPending(provider);
    try {
      const { authorization_url } = await getOAuthLoginAuthorizeUrl(provider);
      if (!isHttpsUrl(authorization_url)) {
        toast.error(t("auth.errors.unsafeAuthorizationUrl"));
        setPending(null);
        return;
      }
      setOAuthFlow("login");
      window.location.href = authorization_url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      setPending(null);
    }
  };

  return (
    <div className="flex w-full max-w-sm flex-col gap-2">
      {enabled.map((provider) => (
        <Button
          key={provider}
          variant="outline"
          onClick={() => void handleClick(provider)}
          disabled={pending !== null}
        >
          {pending === provider && <Loader2 className="size-3.5 animate-spin" />}
          {t("auth.oauth.continueWith", { provider: providerLabels[provider] })}
        </Button>
      ))}
    </div>
  );
}
