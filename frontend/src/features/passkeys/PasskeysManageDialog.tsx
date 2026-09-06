import { startRegistration } from "@simplewebauthn/browser";
import { Fingerprint, Pencil, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  deletePasskey,
  getPasskeyRegistrationOptions,
  getPasskeys,
  renamePasskey,
  verifyPasskeyRegistration,
  type Passkey,
} from "@entities/auth/passkeys";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";

interface PasskeysManageDialogProps {
  onClose: () => void;
}

export function PasskeysManageDialog({ onClose }: PasskeysManageDialogProps) {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(getPasskeys);
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = async () => {
    setIsAdding(true);
    try {
      const optionsJSON = await getPasskeyRegistrationOptions();
      const response = await startRegistration({ optionsJSON: optionsJSON as never });
      const name = window.prompt(t("profile.passkeys.namePrompt"), "") || null;
      await verifyPasskeyRegistration(response as unknown as Record<string, unknown>, name);
      reload();
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

  const handleRename = async (passkey: Passkey) => {
    const name = window.prompt(t("profile.passkeys.namePrompt"), passkey.name);
    if (!name || name === passkey.name) return;
    try {
      await renamePasskey(passkey.id, name);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.renameError")));
    }
  };

  const handleDelete = async (passkey: Passkey) => {
    if (!window.confirm(t("profile.passkeys.deleteConfirm"))) return;
    try {
      await deletePasskey(passkey.id);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.passkeys.deleteError")));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-2xl border border-glass-border bg-surface p-5 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-foreground">{t("profile.passkeys.title")}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          {t("profile.passkeys.description")}
        </p>

        <div className="mt-4 flex flex-col gap-1">
          {state.kind === "loading" && (
            <p className="text-sm text-muted-foreground">{t("profile.passkeys.loading")}</p>
          )}
          {state.kind === "error" && (
            <p className="text-sm text-error">{t("profile.passkeys.loadError")}</p>
          )}
          {state.kind === "ready" && state.data.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("profile.passkeys.empty")}</p>
          )}
          {state.kind === "ready" &&
            state.data.map((passkey) => (
              <div
                key={passkey.id}
                className="flex items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5 hover:bg-white/[0.04]"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                    <Fingerprint className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-foreground">
                      {passkey.name}
                    </p>
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

        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={isAdding}
          className="mt-4 w-full rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isAdding ? t("profile.passkeys.adding") : t("profile.passkeys.addButton")}
        </button>
      </div>
    </div>
  );
}
