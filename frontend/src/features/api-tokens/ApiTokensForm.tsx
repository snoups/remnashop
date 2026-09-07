import { KeyRound, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { type ApiToken, type CreatedApiToken, listApiTokens, revokeApiToken } from "@entities/api-tokens/api";
import { CreateApiTokenDialog } from "@features/api-tokens/CreateApiTokenDialog";
import { RevealSecretDialog } from "@features/api-tokens/RevealSecretDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";

export function ApiTokensForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const catalogState = usePermissionCatalog();
  const [state, reload] = useAsyncResource(listApiTokens);
  const [isCreating, setIsCreating] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [pendingRevoke, setPendingRevoke] = useState<ApiToken | null>(null);

  const handleCreated = (created: CreatedApiToken) => {
    setIsCreating(false);
    setRevealedSecret(created.secret);
    reload();
  };

  const handleRevoke = async (id: number) => {
    try {
      await revokeApiToken(id);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("apiTokens.revokeError")));
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <div className="flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <KeyRound className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("apiTokens.title")}</h2>
            <p className="text-[12.5px] text-muted-foreground">{t("apiTokens.description")}</p>
          </div>
        </div>
        <motion.button
          type="button"
          onClick={() => setIsCreating(true)}
          {...bounceTap(bounceStrength)}
          className="shrink-0 rounded-full bg-accent px-3.5 py-2 text-[12.5px] font-semibold text-primary transition-colors hover:bg-primary/20"
        >
          {t("apiTokens.create")}
        </motion.button>
      </div>

      <div className="mt-3">
        {state.kind === "loading" && <Spinner />}
        {state.kind === "error" && <p className="text-sm text-error">{t("apiTokens.loadError")}</p>}
        {state.kind === "ready" && state.data.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("apiTokens.empty")}</p>
        )}
        {state.kind === "ready" && state.data.length > 0 && (
          <div className="flex flex-col">
            {state.data.map((token) => (
              <div
                key={token.id}
                className="group flex w-full items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5"
              >
                <div>
                  <p className="text-[13px] font-medium text-foreground">{token.name}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {catalogState.kind === "ready" &&
                    token.permissions.length === catalogState.data.length ? (
                      <span className="rounded-full bg-accent px-2 py-0.5 text-[10.5px] font-semibold text-primary">
                        {t("apiTokens.fullAccess")}
                      </span>
                    ) : (
                      token.permissions.map((permission) => (
                        <span
                          key={permission}
                          className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10.5px] font-medium text-muted-foreground"
                        >
                          {t(`permissions.${permission}`)}
                        </span>
                      ))
                    )}
                  </div>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    {token.last_used_at
                      ? t("apiTokens.lastUsed", { date: new Date(token.last_used_at).toLocaleString() })
                      : t("apiTokens.neverUsed")}
                    {" · "}
                    {t("apiTokens.createdAt", { date: new Date(token.created_at).toLocaleString() })}
                    {" · "}
                    {token.expires_at
                      ? t("apiTokens.expiresAt", { date: new Date(token.expires_at).toLocaleString() })
                      : t("apiTokens.neverExpires")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPendingRevoke(token)}
                  aria-label={t("apiTokens.revoke")}
                  title={t("apiTokens.revoke")}
                  className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {isCreating && (
        <CreateApiTokenDialog onCreated={handleCreated} onCancel={() => setIsCreating(false)} />
      )}

      {revealedSecret && (
        <RevealSecretDialog secret={revealedSecret} onDone={() => setRevealedSecret(null)} />
      )}

      {pendingRevoke && (
        <ConfirmDialog
          title={t("apiTokens.revokeTitle")}
          message={t("apiTokens.revokeConfirm")}
          confirmLabel={t("apiTokens.revoke")}
          cancelLabel={t("apiTokens.cancel")}
          danger
          onConfirm={() => {
            void handleRevoke(pendingRevoke.id);
            setPendingRevoke(null);
          }}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </div>
  );
}
