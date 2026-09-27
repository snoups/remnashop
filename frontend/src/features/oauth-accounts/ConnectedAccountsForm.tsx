import { startRegistration } from "@simplewebauthn/browser";
import { Fingerprint, Inbox, KeyRound, Link2, Pencil, Trash2, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { getAuthStatus } from "@entities/auth/api";
import {
  disconnectOAuth,
  getOAuthConnectAuthorizeUrl,
  listConnectedAccounts,
  type OAuthIdentity,
  type OAuthProvider,
} from "@entities/auth/oauth";
import {
  deletePasskey,
  getPasskeyRegistrationOptions,
  getPasskeys,
  renamePasskey,
  verifyPasskeyRegistration,
  type Passkey,
} from "@entities/auth/passkeys";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { isHttpsUrl } from "@shared/lib/external-links";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";

const PROVIDERS: OAuthProvider[] = ["github", "telegram", "oidc"];

const PROVIDER_ICONS: Record<OAuthProvider, ComponentType<{ className?: string }>> = {
  github: GithubIcon,
  telegram: TelegramIcon,
  oidc: KeyRound,
};

interface ConnectedAccountsData {
  identities: OAuthIdentity[];
  oidcDisplayName: string | null;
  passkeys: Passkey[];
}

async function loadConnectedAccountsData(signal?: AbortSignal): Promise<ConnectedAccountsData> {
  const [identities, status, passkeys] = await Promise.all([
    listConnectedAccounts(signal),
    getAuthStatus(signal),
    getPasskeys(signal),
  ]);
  return { identities, oidcDisplayName: status.oidc_display_name, passkeys };
}

export function ConnectedAccountsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(loadConnectedAccountsData);

  const handleConnect = async (provider: OAuthProvider) => {
    try {
      const { authorization_url } = await getOAuthConnectAuthorizeUrl(provider);
      if (!isHttpsUrl(authorization_url)) {
        toast.error(t("auth.errors.unsafeAuthorizationUrl"));
        return;
      }
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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Link2 className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("profile.oauthAccounts.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("profile.oauthAccounts.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      <div className="mt-4 flex flex-col divide-y divide-border/50">
        {state.kind === "loading" && (
          <Spinner />
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
        {state.kind === "ready" && <PasskeyRow passkeys={state.data.passkeys} onChange={reload} />}
      </div>
    </div>
  );
}

interface PasskeyRowProps {
  passkeys: Passkey[];
  onChange: () => void;
}

function PasskeyRow({ passkeys, onChange }: PasskeyRowProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isAdding, setIsAdding] = useState(false);
  const [isManaging, setIsManaging] = useState(false);

  const handleAdd = async () => {
    setIsAdding(true);
    try {
      const optionsJSON = await getPasskeyRegistrationOptions();
      const response = await startRegistration({ optionsJSON: optionsJSON as never });
      const name = window.prompt(t("profile.passkeys.namePrompt"), "") || null;
      await verifyPasskeyRegistration(response as unknown as Record<string, unknown>, name);
      onChange();
    } catch (err) {
      if (err instanceof Error && err.name === "NotAllowedError") {
        toast.error(t("profile.passkeys.cancelled"));
      } else if (err instanceof Error && err.name === "NotSupportedError") {
        toast.error(t("profile.passkeys.notSupported"));
      } else {
        toast.error(getErrorMessage(err, t("profile.passkeys.addError")));
      }
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
      <div className="flex items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
          <Fingerprint className="size-4" />
        </div>
        <div>
          <p className="text-[13px] font-medium text-foreground">{t("profile.passkeys.title")}</p>
          <p className="text-[12px] text-muted-foreground">
            {passkeys.length > 0
              ? t("profile.oauthAccounts.connected")
              : t("profile.oauthAccounts.notConnected")}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        {passkeys.length > 0 && (
          <button
            type="button"
            onClick={() => setIsManaging(true)}
            className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground/90 transition-colors hover:bg-white/5"
          >
            {t("profile.passkeys.manage")}
          </button>
        )}
        <motion.button
          type="button"
          onClick={() => void handleAdd()}
          disabled={isAdding}
          {...bounceTap(bounceStrength)}
          className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isAdding ? t("profile.passkeys.adding") : t("profile.passkeys.addButton")}
        </motion.button>
      </div>

      {isManaging && (
        <Modal onClose={() => setIsManaging(false)} size="sm">
          <PasskeysManageDialogBody passkeys={passkeys} onChange={onChange} />
        </Modal>
      )}
    </div>
  );
}

interface PasskeysManageDialogBodyProps {
  passkeys: Passkey[];
  onChange: () => void;
}

function PasskeysManageDialogBody({ passkeys, onChange }: PasskeysManageDialogBodyProps) {
  const { t } = useTranslation();
  const close = useModalClose();

  const handleRename = async (passkey: Passkey) => {
    const name = window.prompt(t("profile.passkeys.namePrompt"), passkey.name);
    if (!name || name === passkey.name) return;
    try {
      await renamePasskey(passkey.id, name);
      onChange();
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.renameError")));
    }
  };

  const handleDelete = async (passkey: Passkey) => {
    if (!window.confirm(t("profile.passkeys.deleteConfirm"))) return;
    try {
      await deletePasskey(passkey.id);
      onChange();
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.deleteError")));
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Fingerprint className="size-4" />
          </div>
          {t("profile.passkeys.title")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.passkeys.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex flex-col divide-y divide-border/50 px-5 pb-5 pt-4">
        {passkeys.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
            <Inbox className="size-5" />
            <p className="text-sm">{t("profile.passkeys.empty")}</p>
          </div>
        )}
        {passkeys.map((passkey) => (
          <div
            key={passkey.id}
            className="flex items-center justify-between gap-3 rounded-full py-1.5 hover:bg-white/[0.04]"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                <Fingerprint className="size-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-foreground">{passkey.name}</p>
                <p className="text-[12px] text-muted-foreground">
                  {passkey.last_used_at
                    ? t("profile.passkeys.lastUsed", {
                        date: new Date(passkey.last_used_at).toLocaleDateString(),
                      })
                    : t("profile.passkeys.neverUsed")}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 gap-1">
              <button
                type="button"
                onClick={() => void handleRename(passkey)}
                aria-label={t("profile.passkeys.rename")}
                className="rounded-full p-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground"
              >
                <Pencil className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(passkey)}
                aria-label={t("profile.passkeys.delete")}
                className="rounded-full p-1.5 text-error/80 hover:bg-white/5 hover:text-error"
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
