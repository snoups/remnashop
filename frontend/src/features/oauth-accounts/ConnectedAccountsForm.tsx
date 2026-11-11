import { GLASS_DIALOG_FOOTER_CLASS, GLASS_DIALOG_PAD_CLASS } from "@shared/ui/classes";
import { startRegistration } from "@simplewebauthn/browser";
import { Fingerprint, KeyRound, Link2, Pencil, Trash2 } from "lucide-react";
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
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { formatDate } from "@shared/lib/relative-time";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

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
  /** providers an admin can sign in with now: only those get a row */
  usableProviders: OAuthProvider[];
  isPasskeyEnabled: boolean;
}

async function loadConnectedAccountsData(signal?: AbortSignal): Promise<ConnectedAccountsData> {
  const [identities, status, passkeys] = await Promise.all([
    listConnectedAccounts(signal),
    getAuthStatus(signal),
    getPasskeys(signal),
  ]);
  return {
    identities,
    oidcDisplayName: status.oidc_display_name,
    passkeys,
    usableProviders: PROVIDERS.filter((provider) => status.oauth_providers[provider]),
    isPasskeyEnabled: status.is_passkey_login_enabled,
  };
}

export function ConnectedAccountsForm() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(loadConnectedAccountsData);
  // a successful connect keeps it set: the page is navigating away to the provider
  const [pendingProvider, setPendingProvider] = useState<OAuthProvider | null>(null);
  const [confirmTelegram, setConfirmTelegram] = useState(false);

  const handleConnect = async (provider: OAuthProvider) => {
    setPendingProvider(provider);
    try {
      const { url } = await getOAuthConnectAuthorizeUrl(provider);
      if (!isHttpsUrl(url)) {
        toast.error(t("auth.errors.unsafeAuthorizationUrl"));
        setPendingProvider(null);
        return;
      }
      setOAuthFlow("connect");
      window.location.href = url;
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      setPendingProvider(null);
    }
  };

  const handleDisconnect = async (provider: OAuthProvider) => {
    setConfirmTelegram(false);
    setPendingProvider(provider);
    try {
      await disconnectOAuth(provider);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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

  // no sign-in without a password is set up: nothing to link
  if (
    state.kind === "ready" &&
    state.data.usableProviders.length === 0 &&
    !state.data.isPasskeyEnabled &&
    state.data.passkeys.length === 0
  ) {
    return null;
  }

  return (
    <Section icon={Link2} title={t("profile.oauthAccounts.title")} description={t("profile.oauthAccounts.description")}>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <SectionRows>
          {state.data.usableProviders.map((provider) => {
            const identity = state.data.identities.find((item) => item.provider.toLowerCase() === provider);
            return (
              <Row
                key={provider}
                icon={PROVIDER_ICONS[provider]}
                label={providerLabels[provider]}
                description={
                  identity
                    ? identity.external_login
                      ? t("profile.oauthAccounts.connectedAs", { login: identity.external_login })
                      : t("profile.oauthAccounts.connected")
                    : t("profile.oauthAccounts.notConnected")
                }
              >
                <Button
                  variant={identity ? "glassDanger" : "glass"}
                  size="sm"
                  onClick={() => {
                    if (!identity) void handleConnect(provider);
                    else if (provider === "telegram") setConfirmTelegram(true);
                    else void handleDisconnect(provider);
                  }}
                  isLoading={pendingProvider === provider}
                  disabled={pendingProvider !== null}
                >
                  {identity ? t("profile.oauthAccounts.disconnect") : t("profile.oauthAccounts.connect")}
                </Button>
              </Row>
            );
          })}
          {/* switched off, keys already added can still be renamed or deleted */}
          {(state.data.isPasskeyEnabled || state.data.passkeys.length > 0) && (
            <PasskeyRow passkeys={state.data.passkeys} canAdd={state.data.isPasskeyEnabled} onChange={reload} />
          )}
        </SectionRows>
      )}
      {confirmTelegram && (
        <ConfirmDialog
          title={t("profile.oauthAccounts.disconnectTelegramTitle")}
          message={t("profile.oauthAccounts.disconnectTelegramWarning")}
          confirmLabel={t("profile.oauthAccounts.disconnect")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleDisconnect("telegram")}
          onCancel={() => setConfirmTelegram(false)}
        />
      )}
    </Section>
  );
}

interface PasskeyRowProps {
  passkeys: Passkey[];
  canAdd: boolean;
  onChange: () => void;
}

function PasskeyRow({ passkeys, canAdd, onChange }: PasskeyRowProps) {
  const { t } = useTranslation();
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isManaging, setIsManaging] = useState(false);

  return (
    <>
      <Row
        icon={Fingerprint}
        label={t("profile.passkeys.title")}
        description={passkeys.length > 0 ? t("profile.oauthAccounts.connected") : t("profile.oauthAccounts.notConnected")}
      >
        {passkeys.length > 0 && (
          <Button variant="glass" size="sm" onClick={() => setIsManaging(true)}>
            {t("profile.passkeys.manage")}
          </Button>
        )}
        {canAdd && (
          <Button variant="glass" size="sm" onClick={() => setIsAddOpen(true)}>
            {t("profile.passkeys.addButton")}
          </Button>
        )}
      </Row>

      {isAddOpen && (
        <Modal onClose={() => setIsAddOpen(false)} size="sm">
          <PasskeyAddDialogBody onAdded={onChange} />
        </Modal>
      )}

      {isManaging && (
        <Modal onClose={() => setIsManaging(false)} size="sm">
          <PasskeysManageDialogBody passkeys={passkeys} onChange={onChange} />
        </Modal>
      )}
    </>
  );
}

/** The name first, then the browser's own passkey prompt; the name may stay empty. */
function PasskeyAddDialogBody({ onAdded }: { onAdded: () => void }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [name, setName] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsAdding(true);
    try {
      const optionsJSON = await getPasskeyRegistrationOptions();
      const response = await startRegistration({ optionsJSON: optionsJSON as never });
      await verifyPasskeyRegistration(response as unknown as Record<string, unknown>, name.trim() || null);
      onAdded();
      close();
    } catch (err) {
      if (err instanceof Error && err.name === "NotAllowedError") {
        toast.error(t("profile.passkeys.cancelled"));
      } else if (err instanceof Error && err.name === "NotSupportedError") {
        toast.error(t("profile.passkeys.notSupported"));
      } else {
        toast.error(getErrorMessage(err, t("profile.passkeys.addError")));
      }
      setIsAdding(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Fingerprint} title={t("profile.passkeys.addButton")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-4">
          <Field label={t("profile.passkeys.namePrompt")} htmlFor="passkey-add-name" hint={t("profile.passkeys.nameHint")}>
            <Input
              id="passkey-add-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("profile.passkeys.namePlaceholder")}
              autoFocus
            />
          </Field>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isAdding}>
            {isAdding ? t("profile.passkeys.adding") : t("common.add")}
          </Button>
        </div>
      </form>
    </>
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

      <div className={GLASS_DIALOG_PAD_CLASS}>
        <DialogCard>
          {passkeys.length === 0 && <EmptyState text={t("profile.passkeys.empty")} />}
          <SectionRows flush>
          {passkeys.map((passkey) => (
            <Row
              key={passkey.id}
              icon={Fingerprint}
              label={<span className="min-w-0 truncate">{passkey.name}</span>}
              description={
                passkey.last_used_at
                  ? t("profile.passkeys.lastUsed", { date: formatDate(passkey.last_used_at, i18n.language) })
                  : t("profile.passkeys.neverUsed")
              }
            >
              <IconButton size="8" onClick={() => setRenameTarget(passkey)} disabled={pendingAction !== null}>
                <Pencil className="size-4" />
              </IconButton>
              <IconButton
                size="8"
                tone="danger"
                onClick={() => setDeleteTarget(passkey)}
                disabled={pendingAction !== null}
                isLoading={pendingAction === `delete:${passkey.id}`}
              >
                <Trash2 className="size-4" />
              </IconButton>
            </Row>
          ))}
          </SectionRows>
        </DialogCard>
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
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
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
        <div className="flex flex-col gap-3 p-4">
          <Field label={t("profile.passkeys.namePrompt")} htmlFor="passkey-rename" required>
            <Input id="passkey-rename" value={value} onChange={(event) => setValue(event.target.value)} autoFocus />
          </Field>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isSubmitting} disabled={!trimmed}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
