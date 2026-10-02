import { startRegistration } from "@simplewebauthn/browser";
import { Fingerprint, KeyRound, Link2, Loader2, Pencil, Trash2 } from "lucide-react";
import { useState, type ComponentType, type FormEvent } from "react";
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
import { isHttpsUrl } from "@shared/lib/external-links";
import { setOAuthFlow } from "@shared/lib/oauth-flow";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { EmptyState } from "@shared/ui/EmptyState";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Spinner } from "@shared/ui/Spinner";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Card } from "@shared/ui/Card";
import { Button } from "@shared/ui/Button";
import { formatDate } from "@shared/lib/relative-time";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Field } from "@shared/ui/Field";
import { TextInput } from "@shared/ui/TextInput";

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
  const [state, reload] = useAsyncResource(loadConnectedAccountsData);
  // a successful connect keeps it set: the page is navigating away to the provider
  const [pendingProvider, setPendingProvider] = useState<OAuthProvider | null>(null);

  const handleConnect = async (provider: OAuthProvider) => {
    setPendingProvider(provider);
    try {
      const { authorization_url } = await getOAuthConnectAuthorizeUrl(provider);
      if (!isHttpsUrl(authorization_url)) {
        toast.error(t("auth.errors.unsafeAuthorizationUrl"));
        setPendingProvider(null);
        return;
      }
      setOAuthFlow("connect");
      window.location.href = authorization_url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      setPendingProvider(null);
    }
  };

  const handleDisconnect = async (provider: OAuthProvider) => {
    setPendingProvider(provider);
    try {
      await disconnectOAuth(provider);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setPendingProvider(null);
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
    <Card>
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
          <Spinner size="card" />
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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    void (identity ? handleDisconnect(provider) : handleConnect(provider))
                  }
                  disabled={pendingProvider !== null}
                >
                  {pendingProvider === provider && <Loader2 className="size-3.5 animate-spin" />}
                  {identity ? t("profile.oauthAccounts.disconnect") : t("profile.oauthAccounts.connect")}
                </Button>
              </div>
            );
          })}
        {state.kind === "ready" && <PasskeyRow passkeys={state.data.passkeys} onChange={reload} />}
      </div>
    </Card>
  );
}

interface PasskeyRowProps {
  passkeys: Passkey[];
  onChange: () => void;
}

function PasskeyRow({ passkeys, onChange }: PasskeyRowProps) {
  const { t } = useTranslation();
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsManaging(true)}
          >
            {t("profile.passkeys.manage")}
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleAdd()}
          disabled={isAdding}
        >
          {isAdding ? t("profile.passkeys.adding") : t("profile.passkeys.addButton")}
        </Button>
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
  const { t, i18n } = useTranslation();

  // "delete:<id>" while that request is in flight
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<Passkey | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Passkey | null>(null);

  const handleRename = async (passkey: Passkey, name: string): Promise<boolean> => {
    if (name === passkey.name) return true;
    try {
      await renamePasskey(passkey.id, name);
      onChange();
      return true;
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.renameError")));
      return false;
    }
  };

  const handleDelete = async (passkey: Passkey) => {
    setPendingAction(`delete:${passkey.id}`);
    try {
      await deletePasskey(passkey.id);
      onChange();
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.deleteError")));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <>
      <DialogHeader icon={Fingerprint} title={t("profile.passkeys.title")} />

      <div className="flex flex-col divide-y divide-border/50 px-5 pb-5 pt-4">
        {passkeys.length === 0 && (
          <EmptyState text={t("profile.passkeys.empty")} />
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
                        date: formatDate(passkey.last_used_at, i18n.language),
                      })
                    : t("profile.passkeys.neverUsed")}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 gap-1">
              <button
                type="button"
                onClick={() => setRenameTarget(passkey)}
                disabled={pendingAction !== null}
                className="rounded-full p-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Pencil className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => setDeleteTarget(passkey)}
                disabled={pendingAction !== null}
                className="rounded-full p-1.5 text-error/80 hover:bg-white/5 hover:text-error disabled:cursor-not-allowed disabled:opacity-60"
              >
                {pendingAction === `delete:${passkey.id}` ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Trash2 className="size-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      {renameTarget && (
        <PasskeyRenameDialog
          name={renameTarget.name}
          onRename={(name) => handleRename(renameTarget, name)}
          onClose={() => setRenameTarget(null)}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={t("profile.passkeys.deleteTitle")}
          message={t("profile.passkeys.deleteConfirm")}
          confirmLabel={t("profile.passkeys.delete")}
          cancelLabel={t("profile.passkeys.cancel")}
          danger
          onConfirm={() => {
            void handleDelete(deleteTarget);
            setDeleteTarget(null);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}

interface PasskeyRenameDialogProps {
  name: string;
  /** resolves true once saved; false keeps the dialog open with the typed name */
  onRename: (name: string) => Promise<boolean>;
  onClose: () => void;
}

function PasskeyRenameDialog({ name, onRename, onClose }: PasskeyRenameDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <PasskeyRenameDialogBody name={name} onRename={onRename} />
    </Modal>
  );
}

function PasskeyRenameDialogBody({ name, onRename }: Omit<PasskeyRenameDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [value, setValue] = useState(name);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const trimmed = value.trim();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    setIsSubmitting(true);
    const saved = await onRename(trimmed);
    setIsSubmitting(false);
    if (saved) close();
  };

  return (
    <>
      <DialogHeader icon={Pencil} title={t("profile.passkeys.renameTitle")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        {/* small form, nothing scrolls: the buttons sit under the fields, no footer */}
        <div className="flex flex-col gap-3 p-4">
          <Card variant="form">
            <Field label={t("profile.passkeys.namePrompt")} htmlFor="passkey-rename" required>
              <TextInput
                id="passkey-rename"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                autoFocus
                required
              />
            </Field>
          </Card>
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={close}>
              {t("profile.passkeys.cancel")}
            </Button>
            <Button variant="accent" type="submit" disabled={isSubmitting || !trimmed}>
              {isSubmitting && <Loader2 className="size-3.5 animate-spin" />}
              {t("profile.passkeys.save")}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
