import { KeyRound, Loader2 } from "lucide-react";
import { useState } from "react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { getOAuthLoginAuthorizeUrl, OAUTH_PROVIDERS, type OAuthProvider } from "@entities/auth/oauth";
import { isHttpsUrl } from "@shared/lib/external-links";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";

const PROVIDER_ICONS: Record<OAuthProvider, ComponentType<{ className?: string }>> = {
  github: GithubIcon,
  telegram: TelegramIcon,
  oidc: KeyRound,
};

interface OAuthLoginButtonsProps {
  oauthProviders: Record<string, boolean>;
  oidcDisplayName: string | null;
  // provider name only, for the two-column layout
  compact?: boolean;
}

export function OAuthLoginButtons({ oauthProviders, oidcDisplayName, compact = false }: OAuthLoginButtonsProps) {
  const { t } = useTranslation();
  // stays set on success: the page is about to navigate away to the provider
  const [pending, setPending] = useState<OAuthProvider | null>(null);

  const providerLabels: Record<OAuthProvider, string> = {
    github: t("profile.oauthAccounts.github"),
    telegram: t("profile.oauthAccounts.telegram"),
    oidc: oidcDisplayName || t("profile.oauthAccounts.oidcFallback"),
  };

  const enabled = OAUTH_PROVIDERS.filter((provider) => oauthProviders[provider]);

  if (enabled.length === 0) return null;

  const handleClick = async (provider: OAuthProvider) => {
    setPending(provider);
    try {
      const { url } = await getOAuthLoginAuthorizeUrl(provider);
      if (!isHttpsUrl(url)) {
        toast.error(t("auth.errors.unsafeAuthorizationUrl"));
        setPending(null);
        return;
      }
      setOAuthFlow("login");
      window.location.href = url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      setPending(null);
    }
  };

  return (
    <>
      {enabled.map((provider) => {
        const Icon = pending === provider ? Loader2 : PROVIDER_ICONS[provider];
        return (
          <Button
            key={provider}
            variant="glass"
            onClick={() => void handleClick(provider)}
            disabled={pending !== null}
          >
            <Icon className={pending === provider ? "size-4 animate-spin" : "size-4"} />
            {compact
              ? providerLabels[provider]
              : t("auth.oauth.continueWith", { provider: providerLabels[provider] })}
          </Button>
        );
      })}
    </>
  );
}
