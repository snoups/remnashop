import { Infinity as InfinityIcon, KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useLayoutEffect, useRef, useState } from "react";
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
    <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <KeyRound className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("apiTokens.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("apiTokens.description")}</p>
          </div>
        </div>
        {!(state.kind === "ready" && state.data.length === 0) && (
          <motion.button
            type="button"
            onClick={() => setIsCreating(true)}
            {...bounceTap(bounceStrength)}
            className="ml-auto flex shrink-0 items-center gap-1.5 rounded-full border border-transparent bg-accent px-4 py-1.5 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20"
          >
            <Plus className="size-3.5" />
            {t("apiTokens.create")}
          </motion.button>
        )}
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {state.kind === "loading" && (
        <div className="mt-4">
          <Spinner />
        </div>
      )}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("apiTokens.loadError")}</p>}
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
          <motion.button
            type="button"
            onClick={() => setIsCreating(true)}
            {...bounceTap(bounceStrength)}
            className="mt-1 flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Plus className="size-3.5" />
            {t("apiTokens.createFirst")}
          </motion.button>
        </div>
      )}
      {state.kind === "ready" && state.data.length > 0 && (
        <div className="mt-4 flex flex-col divide-y divide-border/50">
          <div className={`hidden mb-1.5 px-[12.5px] pb-3 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase md:grid ${ROW_GRID}`}>
            <span>{t("apiTokens.columnToken")}</span>
            <span>{t("apiTokens.columnLastUsed")}</span>
            <span>{t("apiTokens.columnExpiry")}</span>
          </div>
          {state.data.map((token) => (
            <ApiTokenRow
              key={token.id}
              token={token}
              isFullAccess={catalogState.kind === "ready" && token.permissions.length === catalogState.data.length}
              onRevoke={() => setPendingRevoke(token)}
            />
          ))}
        </div>
      )}

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

const ROW_GRID = "md:grid-cols-[minmax(0,1fr)_170px_210px_36px] md:gap-5";
const DAY_MS = 86_400_000;
const EXPIRING_SOON_DAYS = 7;
const CHIP_GAP = 4;
const CHIP_CLASS = "rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-muted-foreground";
const MORE_CLASS =
  "rounded-full border border-dashed border-white/[0.18] px-2 py-0.5 text-[11px] font-semibold text-muted-foreground";

function formatAgo(date: Date, language: string): string {
  const rtf = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
  const seconds = (date.getTime() - Date.now()) / 1000;
  if (seconds > -3600) return rtf.format(Math.round(seconds / 60), "minute");
  if (seconds > -86_400) return rtf.format(Math.round(seconds / 3600), "hour");
  return rtf.format(Math.round(seconds / 86_400), "day");
}

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
  const isExpiringSoon = daysLeft !== null && daysLeft <= EXPIRING_SOON_DAYS;
  const areaRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(token.permissions.length);
  const hiddenCount = token.permissions.length - visibleCount;
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
  }, [token.permissions, i18n.language, isFullAccess]);

  return (
    <div
      {...(canExpand && {
        role: "button",
        tabIndex: 0,
        "aria-expanded": isExpanded,
        onClick: toggleExpanded,
        onKeyDown: (event: React.KeyboardEvent) => {
          if (event.target !== event.currentTarget || (event.key !== "Enter" && event.key !== " ")) return;
          event.preventDefault();
          toggleExpanded();
        },
      })}
      className={`grid grid-cols-[minmax(0,1fr)_36px] items-start gap-3 px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04] ${isExpanded ? "rounded-2xl" : "rounded-full"} ${canExpand ? "cursor-pointer" : ""} ${ROW_GRID}`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <div
          className={`flex size-8 shrink-0 items-center justify-center rounded-full ${isExpiringSoon ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}
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
              <div aria-hidden ref={measureRef} className="invisible absolute flex gap-1">
                {token.permissions.map((permission) => (
                  <span key={permission} className={`${CHIP_CLASS} whitespace-nowrap`}>
                    {t(`permissions.${permission}`)}
                  </span>
                ))}
                <span className={MORE_CLASS}>+{token.permissions.length}</span>
              </div>
              {(isExpanded ? token.permissions : token.permissions.slice(0, visibleCount)).map((permission) => (
                <span key={permission} className={`${CHIP_CLASS} shrink-0 whitespace-nowrap`}>
                  {t(`permissions.${permission}`)}
                </span>
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
          <>
            <p className="text-sm text-foreground">{formatAgo(new Date(token.last_used_at), i18n.language)}</p>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">
              {new Date(token.last_used_at).toLocaleString(i18n.language)}
            </p>
          </>
        ) : (
          <p className="text-sm leading-8 text-muted-foreground italic">{t("apiTokens.neverUsed")}</p>
        )}
      </div>

      <div className="col-span-2 pl-11 md:col-span-1 md:pl-0">
        {daysLeft !== null && totalDays !== null ? (
          <>
            <div className="flex justify-between gap-2 text-sm">
              <span className={isExpiringSoon ? "text-warning" : "text-foreground"}>
                {new Intl.RelativeTimeFormat(i18n.language, { numeric: "auto" }).format(daysLeft, "day")}
              </span>
              <span className="text-[12.5px] text-muted-foreground">
                {t("apiTokens.ofDays", { count: totalDays })}
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
          <p className="flex h-8 items-center gap-1.5 text-sm text-muted-foreground">
            <InfinityIcon className="size-3.5" />
            {t("apiTokens.neverExpires")}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onRevoke();
        }}
        aria-label={t("apiTokens.revoke")}
        className="col-start-2 row-start-1 flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error md:col-start-4"
      >
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}
