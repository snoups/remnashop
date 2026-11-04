import { BookOpen, ChevronDown, Infinity as InfinityIcon, KeyRound, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PermissionCatalogEntry } from "@entities/admin/api";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { type ApiToken, type CreatedApiToken, issueDocsOtt, listApiTokens, revokeApiToken } from "@entities/api-tokens/api";
import { listedTokenScopes, tokenPreset, tokenScopeLabel } from "@entities/api-tokens/scopes";
import { CreateApiTokenDialog } from "@features/api-tokens/CreateApiTokenDialog";
import { getErrorMessage } from "@shared/api/http";
import { DAY_MS } from "@shared/lib/period";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Collapse } from "@shared/ui/Collapse";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Section } from "@shared/ui/glass/Section";
import { Tag } from "@shared/ui/Tag";
import { IconButton } from "@shared/ui/IconButton";
import { OneTimeSecretDialog } from "@shared/ui/OneTimeSecretDialog";
import { Pressable } from "@shared/ui/Pressable";
import { Spinner } from "@shared/ui/Spinner";

export function ApiTokensForm() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listApiTokens);
  const catalogState = usePermissionCatalog();
  const catalog = catalogState.kind === "ready" ? catalogState.data : null;
  const [isCreating, setIsCreating] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [pendingRevoke, setPendingRevoke] = useState<ApiToken | null>(null);

  const handleCreated = (created: CreatedApiToken) => {
    setIsCreating(false);
    setRevealedSecret(created.secret);
    reload();
  };

  const openDocs = async () => {
    // opened before the await: a window opened after it counts as a popup
    const docsWindow = window.open("", "_blank");
    try {
      const ott = await issueDocsOtt();
      if (docsWindow) docsWindow.location.href = `/api/v1/docs?ott=${encodeURIComponent(ott)}`;
    } catch (err) {
      docsWindow?.close();
      toast.error(getErrorMessage(err, t("apiTokens.docsError")));
    }
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
    <Section
      icon={KeyRound}
      title={t("apiTokens.title")}
      description={t("apiTokens.description")}
      aside={
        <>
          <Button variant="glass" icon={BookOpen} onClick={() => void openDocs()}>
            {t("apiTokens.docs")}
          </Button>
          {!(state.kind === "ready" && state.data.length === 0) && (
            <Button variant="glassAccent" icon={Plus} onClick={() => setIsCreating(true)}>
              {t("common.create")}
            </Button>
          )}
        </>
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.data.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <p className="max-w-md text-[12px] leading-relaxed text-muted-foreground">{t("apiTokens.emptyHint")}</p>
          <code className="glass-well flex h-9 items-center rounded-full px-3.5 font-mono text-[12px] text-muted-foreground">
            Authorization: Bearer &lt;token&gt;
          </code>
          <Button variant="glassAccent" icon={Plus} onClick={() => setIsCreating(true)}>
            {t("apiTokens.createFirst")}
          </Button>
        </div>
      )}
      {state.kind === "ready" && state.data.length > 0 && (
        <div className="mt-4 flex flex-col divide-y divide-border/50">
          {state.data.map((token) => (
            <ApiTokenRow
              key={token.id}
              token={token}
              catalog={catalog}
              onRevoke={() => setPendingRevoke(token)}
            />
          ))}
        </div>
      )}

      {isCreating && <CreateApiTokenDialog onCreated={handleCreated} onCancel={() => setIsCreating(false)} />}

      {revealedSecret && (
        <OneTimeSecretDialog
          title={t("apiTokens.secretTitle")}
          value={revealedSecret}
          onDone={() => setRevealedSecret(null)}
        />
      )}

      {pendingRevoke && (
        <ConfirmDialog
          title={t("apiTokens.revokeTitle")}
          message={t("apiTokens.revokeConfirm")}
          confirmLabel={t("apiTokens.revoke")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            void handleRevoke(pendingRevoke.id);
            setPendingRevoke(null);
          }}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </Section>
  );
}

const ROW_GRID = "md:grid-cols-[minmax(0,1fr)_170px_210px_36px] md:gap-5";
const EXPIRING_SOON_DAYS = 7;

interface ApiTokenRowProps {
  token: ApiToken;
  catalog: PermissionCatalogEntry[] | null;
  onRevoke: () => void;
}

function ApiTokenRow({ token, catalog, onRevoke }: ApiTokenRowProps) {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const preset = tokenPreset(token.scopes, catalog);

  const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
  const daysLeft = expiresAt ? Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / DAY_MS)) : null;
  const totalDays = expiresAt
    ? Math.max(1, Math.round((expiresAt.getTime() - new Date(token.created_at).getTime()) / DAY_MS))
    : null;
  const isExpired = expiresAt !== null && expiresAt.getTime() <= Date.now();
  const isExpiringSoon = !isExpired && daysLeft !== null && daysLeft <= EXPIRING_SOON_DAYS;
  return (
    <div className={isOpen ? "rounded-[30px]" : "rounded-full"}>
      <Pressable
        as="div"
        onClick={() => setIsOpen((open) => !open)}
        className={`grid grid-cols-[minmax(0,1fr)_36px] items-start min-h-15 gap-3 rounded-full p-3.5 transition-colors hover:bg-white/[0.04] ${ROW_GRID}`}
      >
        <div className="flex min-w-0 items-start gap-3">
          <div
            className={`flex size-8 shrink-0 items-center justify-center rounded-full ${isExpired ? "bg-error/10 text-error" : isExpiringSoon ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}
          >
            <KeyRound className="size-4" />
          </div>
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <p className="min-w-0 truncate text-[13px] font-medium leading-8 text-foreground">{token.name}</p>
            {preset && <Tag>{t(`apiTokens.${preset}`)}</Tag>}
          </div>
          <span className="flex size-8 shrink-0 items-center justify-center">
            <ChevronDown className={`size-3.5 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
          </span>
        </div>

        <div className="col-span-2 pl-11 md:col-span-1 md:pl-0">
          {token.last_used_at ? (
            <p className="truncate text-[13px] leading-8 text-foreground">
              {formatDateTime(token.last_used_at, i18n.language)}
            </p>
          ) : (
            <p className="text-[13px] leading-8 text-muted-foreground italic">{t("apiTokens.neverUsed")}</p>
          )}
        </div>

        <div className="col-span-2 pl-11 md:col-span-1 md:pl-0">
          {daysLeft !== null && totalDays !== null ? (
            <>
              <div className="flex justify-between gap-2 text-[13px]">
                <span className={`${isExpired ? "text-error" : isExpiringSoon ? "text-warning" : "text-foreground"}`}>
                  {isExpired ? t("apiTokens.expired") : t("apiTokens.daysLeft", { count: daysLeft })}
                </span>
                <span className="text-[12px] text-muted-foreground">
                  {totalDays}
                </span>
              </div>
              <div className="mt-2 h-1 rounded-full glass-track">
                <div
                  className={`h-1 rounded-full ${isExpiringSoon ? "bg-warning" : "bg-primary"}`}
                  style={{ width: `${Math.min(100, (daysLeft / totalDays) * 100)}%` }}
                />
              </div>
            </>
          ) : (
            <p className="flex h-8 items-center gap-1.5 text-[13px] text-foreground">
              <InfinityIcon className="size-3.5" />
              {t("apiTokens.neverExpires")}
            </p>
          )}
        </div>

        <IconButton size="8" tone="danger" className="col-start-2 row-start-1 justify-self-end md:col-start-4"
          onClick={(event) => {
            event.stopPropagation();
            onRevoke();
          }}
        >
          <Trash2 className="size-4" />
        </IconButton>
      </Pressable>
      <Collapse open={isOpen} className="flex flex-col gap-3 px-3.5 pb-3.5 pt-1">
        <div className="flex flex-wrap gap-1.5">
          {listedTokenScopes(token.scopes, catalog).map((scope) => (
            <Tag key={scope}>{tokenScopeLabel(scope, t)}</Tag>
          ))}
          {token.ip_allowlist.length > 0 && <Tag>{t("apiTokens.ipRestricted", { n: token.ip_allowlist.length })}</Tag>}
        </div>
      </Collapse>
    </div>
  );
}
