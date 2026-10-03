import { BookOpen, Infinity as InfinityIcon, KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { type ApiToken, type CreatedApiToken, issueDocsOtt, listApiTokens, revokeApiToken } from "@entities/api-tokens/api";
import { SCOPE_WILDCARD, tokenScopeLabel } from "@entities/api-tokens/scopes";
import { CreateApiTokenDialog } from "@features/api-tokens/CreateApiTokenDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Tag } from "@shared/ui/Tag";
import { Card } from "@shared/ui/Card";
import { IconButton } from "@shared/ui/IconButton";
import { OneTimeSecretDialog } from "@shared/ui/OneTimeSecretDialog";

export function ApiTokensForm() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listApiTokens);
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
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground">
            <KeyRound className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("apiTokens.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("apiTokens.description")}</p>
          </div>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" onClick={() => void openDocs()}>
            <BookOpen className="size-3.5" />
            {t("apiTokens.docs")}
          </Button>
          {!(state.kind === "ready" && state.data.length === 0) && (
            <Button variant="accent" onClick={() => setIsCreating(true)}>
              <Plus className="size-3.5" />
              {t("common.create")}
            </Button>
          )}
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {state.kind === "loading" && (
        <div className="mt-4">
          <Spinner size="card" />
        </div>
      )}
      {state.kind === "error" && <ErrorState text={t("apiTokens.loadError")} />}
      {state.kind === "ready" && state.data.length === 0 && (
        <div className="flex flex-col items-center gap-3.5 -mx-4 -mb-4 px-4 pt-8 pb-10 text-center">
          <div>
            <p className="text-sm font-bold text-foreground">{t("apiTokens.empty")}</p>
            <p className="mx-auto mt-1.5 max-w-md text-[13px] leading-relaxed text-muted-foreground">
              {t("apiTokens.emptyHint")}
            </p>
          </div>
          <code className="rounded-xl border border-white/[0.07] bg-black/35 px-3.5 py-2 font-mono text-xs text-muted-foreground">
            Authorization: Bearer &lt;token&gt;
          </code>
          <Button
            variant="accent"
            className="mt-1"
            type="button"
            onClick={() => setIsCreating(true)}
          >
            <Plus className="size-3.5" />
            {t("apiTokens.createFirst")}
          </Button>
        </div>
      )}
      {state.kind === "ready" && state.data.length > 0 && (
        <div className="mt-4 flex flex-col divide-y divide-border/50">
          <div className={`hidden mb-1.5 px-2.5 pb-3 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase md:grid ${ROW_GRID}`}>
            <span>{t("apiTokens.columnToken")}</span>
            <span>{t("apiTokens.columnLastUsed")}</span>
            <span>{t("apiTokens.columnExpiry")}</span>
          </div>
          {state.data.map((token) => (
            <ApiTokenRow
              key={token.id}
              token={token}
              isFullAccess={token.scopes.includes(SCOPE_WILDCARD)}
              onRevoke={() => setPendingRevoke(token)}
            />
          ))}
        </div>
      )}

      {isCreating && (
        <CreateApiTokenDialog onCreated={handleCreated} onCancel={() => setIsCreating(false)} />
      )}

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
    </Card>
  );
}

const ROW_GRID = "md:grid-cols-[minmax(0,1fr)_170px_210px_36px] md:gap-5";
const DAY_MS = 86_400_000;
const EXPIRING_SOON_DAYS = 7;
const CHIP_GAP = 4;
const MORE_CLASS =
  "rounded-full border border-dashed border-white/[0.18] px-2 py-0.5 text-[11px] font-semibold text-muted-foreground";

interface ApiTokenRowProps {
  token: ApiToken;
  isFullAccess: boolean;
  onRevoke: () => void;
}

function ApiTokenRow({ token, isFullAccess, onRevoke }: ApiTokenRowProps) {
  const { t, i18n } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
  const daysLeft = expiresAt ? Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / DAY_MS)) : null;
  const totalDays = expiresAt
    ? Math.max(1, Math.round((expiresAt.getTime() - new Date(token.created_at).getTime()) / DAY_MS))
    : null;
  const isExpired = expiresAt !== null && expiresAt.getTime() <= Date.now();
  const isExpiringSoon = !isExpired && daysLeft !== null && daysLeft <= EXPIRING_SOON_DAYS;
  const areaRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(token.scopes.length);
  const hiddenCount = token.scopes.length - visibleCount;
  const canExpand = hiddenCount > 0;
  const toggleExpanded = () => setIsExpanded((prev) => !prev);

  // fits as many chips as one line holds, reserving room for the "+N" chip
  useLayoutEffect(() => {
    const area = areaRef.current;
    const measure = measureRef.current;
    if (!area || !measure) return;
    const fit = () => {
      const chips = Array.from(measure.children) as HTMLElement[];
      const more = chips.pop();
      if (!more) return;
      let used = 0;
      let count = 0;
      for (const [index, chip] of chips.entries()) {
        const width = chip.offsetWidth + (index > 0 ? CHIP_GAP : 0);
        const reserve = index < chips.length - 1 ? CHIP_GAP + more.offsetWidth : 0;
        if (used + width + reserve > area.clientWidth) break;
        used += width;
        count += 1;
      }
      setVisibleCount(count);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(area);
    return () => observer.disconnect();
  }, [token.scopes, i18n.language, isFullAccess]);

  return (
    <div
      {...(canExpand && {
        tabIndex: 0,
        onClick: toggleExpanded,
        onKeyDown: (event: React.KeyboardEvent) => {
          if (event.target !== event.currentTarget || (event.key !== "Enter" && event.key !== " ")) return;
          event.preventDefault();
          toggleExpanded();
        },
      })}
      className={`grid grid-cols-[minmax(0,1fr)_36px] items-start gap-3 px-2.5 py-2.5 transition-colors hover:bg-white/[0.04] ${isExpanded ? "rounded-2xl" : "rounded-full"} ${canExpand ? "cursor-pointer" : ""} ${ROW_GRID}`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <div
          className={`flex size-8 shrink-0 items-center justify-center rounded-full ${isExpired ? "bg-error/10 text-error" : isExpiringSoon ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}
        >
          <KeyRound className="size-4" />
        </div>
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <p className="min-w-0 truncate font-mono leading-8 text-sm font-medium text-foreground">{token.name}</p>
          {isFullAccess ? (
            <span className="mt-1.5 flex shrink-0 items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-foreground">
              <ShieldCheck className="size-3" />
              {t("apiTokens.fullAccess")}
            </span>
          ) : (
            <div
              ref={areaRef}
              className={`relative mt-1.5 flex min-w-0 flex-1 gap-1 ${isExpanded ? "flex-wrap" : "overflow-hidden"}`}
            >
              <div ref={measureRef} className="invisible absolute flex gap-1">
                {token.scopes.map((scope) => (
                  <Tag key={scope}>
                    {tokenScopeLabel(scope, t)}
                  </Tag>
                ))}
                <span className={MORE_CLASS}>+{token.scopes.length}</span>
              </div>
              {(isExpanded ? token.scopes : token.scopes.slice(0, visibleCount)).map((scope) => (
                <Tag key={scope}>
                  {tokenScopeLabel(scope, t)}
                </Tag>
              ))}
              {hiddenCount > 0 && (
                <span className={`${MORE_CLASS} shrink-0`}>
                  {isExpanded ? t("apiTokens.collapse") : `+${hiddenCount}`}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="col-span-2 pl-11 md:col-span-1 md:pl-0">
        {token.last_used_at ? (
          <p className="truncate text-sm leading-8 text-foreground">
            {new Date(token.last_used_at).toLocaleString(i18n.language)}
          </p>
        ) : (
          <p className="text-sm leading-8 text-muted-foreground italic">{t("apiTokens.neverUsed")}</p>
        )}
      </div>

      <div className="col-span-2 pl-11 md:col-span-1 md:pl-0">
        {daysLeft !== null && totalDays !== null ? (
          <>
            <div className="flex justify-between gap-2 text-sm">
              <span className={`first-letter:uppercase ${isExpired ? "text-error" : isExpiringSoon ? "text-warning" : "text-foreground"}`}>
                {isExpired
                  ? t("apiTokens.expired")
                  : new Intl.RelativeTimeFormat(i18n.language, { numeric: "always" }).format(daysLeft, "day")}
              </span>
              <span className="text-[12.5px] text-muted-foreground">
                {totalDays}
              </span>
            </div>
            <div className="mt-2 h-1 rounded-full bg-white/[0.08]">
              <div
                className={`h-1 rounded-full ${isExpiringSoon ? "bg-warning" : "bg-primary"}`}
                style={{ width: `${Math.min(100, (daysLeft / totalDays) * 100)}%` }}
              />
            </div>
          </>
        ) : (
          <p className="flex h-8 items-center gap-1.5 text-sm text-foreground">
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
    </div>
  );
}
