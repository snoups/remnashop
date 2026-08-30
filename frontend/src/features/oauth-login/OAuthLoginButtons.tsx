import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { getOAuthLoginAuthorizeUrl, type OAuthProvider } from "@entities/auth/oauth";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";

const PROVIDERS: OAuthProvider[] = ["github", "telegram", "oidc"];

interface OAuthLoginButtonsProps {
  oauthProviders: Record<string, boolean>;
  oidcDisplayName: string | null;
}

export function OAuthLoginButtons({ oauthProviders, oidcDisplayName }: OAuthLoginButtonsProps) {
  const { t } = useTranslation();

  const providerLabels: Record<OAuthProvider, string> = {
    github: t("profile.oauthAccounts.github"),
    telegram: t("profile.oauthAccounts.telegram"),
    oidc: oidcDisplayName || t("profile.oauthAccounts.oidcFallback"),
  };

  const enabled = PROVIDERS.filter((provider) => oauthProviders[provider]);

  if (enabled.length === 0) return null;

  const handleClick = async (provider: OAuthProvider) => {
    try {
      const { authorization_url } = await getOAuthLoginAuthorizeUrl(provider);
      setOAuthFlow("login");
      window.location.href = authorization_url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div className="flex w-full max-w-sm flex-col gap-2">
      {enabled.map((provider) => (
        <button
          key={provider}
          type="button"
          onClick={() => void handleClick(provider)}
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition hover:bg-white/5"
        >
          {t("auth.oauth.continueWith", { provider: providerLabels[provider] })}
        </button>
      ))}
    </div>
  );
}
