import { KeyRound, Link2 } from "lucide-react";
import { motion } from "motion/react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { getAuthStatus } from "@entities/auth/api";
import { getErrorMessage } from "@shared/api/http";
import {
  disconnectOAuth,
  getOAuthConnectAuthorizeUrl,
  listConnectedAccounts,
  type OAuthIdentity,
  type OAuthProvider,
} from "@entities/auth/oauth";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";

const PROVIDERS: OAuthProvider[] = ["github", "telegram", "oidc"];

const PROVIDER_ICONS: Record<OAuthProvider, ComponentType<{ className?: string }>> = {
  github: GithubIcon,
  telegram: TelegramIcon,
  oidc: KeyRound,
};

interface ConnectedAccountsData {
  identities: OAuthIdentity[];
  oidcDisplayName: string | null;
}

async function loadConnectedAccountsData(signal?: AbortSignal): Promise<ConnectedAccountsData> {
  const [identities, status] = await Promise.all([
    listConnectedAccounts(signal),
    getAuthStatus(signal),
  ]);
  return { identities, oidcDisplayName: status.oidc_display_name };
}

export function ConnectedAccountsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(loadConnectedAccountsData);

  const handleConnect = async (provider: OAuthProvider) => {
    try {
      const { authorization_url } = await getOAuthConnectAuthorizeUrl(provider);
      setOAuthFlow("connect");
      window.location.href = authorization_url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleDisconnect = async (provider: OAuthProvider) => {
    try {
      await disconnectOAuth(provider);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const providerLabels: Record<OAuthProvider, string> = {
    github: t("profile.oauthAccounts.github"),
    telegram: t("profile.oauthAccounts.telegram"),
    oidc:
      (state.kind === "ready" && state.data.oidcDisplayName) ||
      t("profile.oauthAccounts.oidcFallback"),
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Link2 className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("profile.oauthAccounts.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("profile.oauthAccounts.description")}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-col">
        {state.kind === "loading" && (
          <p className="text-sm text-muted-foreground">{t("profile.oauthAccounts.loading")}</p>
        )}
        {state.kind === "error" && (
          <p className="text-sm text-error">{t("profile.oauthAccounts.loadError")}</p>
        )}
        {state.kind === "ready" &&
          PROVIDERS.map((provider) => {
            const identity = state.data.identities.find(
              (item) => item.provider.toLowerCase() === provider,
            );
            const Icon = PROVIDER_ICONS[provider];
            return (
              <div
                key={provider}
                className="flex items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex items-center gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                    <Icon className="size-4" />
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-foreground">{providerLabels[provider]}</p>
                    <p className="text-[12px] text-muted-foreground">
                      {identity
                        ? identity.external_login
                          ? t("profile.oauthAccounts.connectedAs", { login: identity.external_login })
                          : t("profile.oauthAccounts.connected")
                        : t("profile.oauthAccounts.notConnected")}
                    </p>
                  </div>
                </div>
                <motion.button
                  type="button"
                  onClick={() =>
                    void (identity ? handleDisconnect(provider) : handleConnect(provider))
                  }
                  {...bounceTap(bounceStrength)}
                  className="shrink-0 rounded-full border border-border px-3 py-1.5 text-sm text-foreground/90 transition-colors hover:bg-white/5"
                >
                  {identity ? t("profile.oauthAccounts.disconnect") : t("profile.oauthAccounts.connect")}
                </motion.button>
              </div>
            );
          })}
      </div>
    </div>
  );
}
