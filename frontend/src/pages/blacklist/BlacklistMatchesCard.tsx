import { ChevronLeft, ChevronRight, SearchX, Unlock, UserX } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  listBlacklistMatches,
  type BlacklistMatch,
  type BlacklistMatchFilters,
  type BlacklistMatchPage,
  type BlacklistMatchUser,
  type BlacklistOrigin,
  unblockBlacklistMatches,
} from "@entities/blacklist/api";
import { PillTabs } from "@shared/ui/PillTabs";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { initials } from "@shared/lib/initials";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { Spinner } from "@shared/ui/Spinner";
import { SearchField } from "@shared/ui/SearchField";
import { IconButton } from "@shared/ui/IconButton";
import { Button } from "@shared/ui/Button";
import { EYEBROW_CLASS } from "@shared/ui/classes";

import { BlacklistCard, KindBadge } from "./BlacklistCard";
import { Pressable } from "@shared/ui/Pressable";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 200;

type Origin = BlacklistMatchFilters["origin"];

function matchOrigins(match: BlacklistMatch): BlacklistOrigin[] {
  const byKey = new Map<string, BlacklistOrigin>();
  for (const hit of match.hits) for (const origin of hit.origins) byKey.set(String(origin.source_id), origin);
  return [...byKey.values()];
}

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: BlacklistMatchPage };

interface BlacklistMatchesCardProps {
  // bumped by the page whenever the blacklist changes
  reloadKey: number;
  canUnblockAll: boolean;
  onUnblocked: () => void;
}

export function BlacklistMatchesCard({ reloadKey, canUnblockAll, onUnblocked }: BlacklistMatchesCardProps) {
  const { t } = useTranslation();
  const [isUnblockConfirmOpen, setIsUnblockConfirmOpen] = useState(false);
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [search, setSearch] = useState("");
  const [origin, setOrigin] = useState<Origin>(undefined);
  const [page, setPage] = useState(1);
  const [detailsUser, setDetailsUser] = useState<BlacklistMatchUser | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);

  useEffect(() => {
    const controller = new AbortController();
    listBlacklistMatches({ search: debouncedSearch || undefined, origin, page, pageSize: PAGE_SIZE }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        // the list shrank under us (entry removed, source disabled)
        if (data.items.length === 0 && page > 1) {
          setPage(1);
          return;
        }
        setState({ kind: "ready", data });
      })
      .catch(() => {
        // keep the last page on screen; only show the error when there's nothing else
        if (!controller.signal.aborted) setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
      });
    return () => controller.abort();
  }, [debouncedSearch, origin, page, reloadKey]);

  const data = state.kind === "ready" ? state.data : null;
  const originLabel = (value: BlacklistOrigin) =>
    value.source_id === null ? t("blacklist.matches.manualOrigin") : (value.source_name ?? "—");
  const pageCount = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const handleUnblockAll = async () => {
    try {
      const result = await unblockBlacklistMatches();
      toast.success(t("blacklist.matches.unblockAll.success", { count: result.unblocked }));
      onUnblocked();
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.matches.unblockAll.error")));
    }
  };

  const changeOrigin = (value: Origin) => {
    setOrigin(value);
    setPage(1);
  };

  return (
    <BlacklistCard
      icon={UserX}
      title={t("blacklist.matches.title")}
      description={t("blacklist.matches.description")}
      action={
        data !== null &&
        data.all_total > 0 && (
          <div className="flex shrink-0 items-center gap-2">
            <span className="flex h-9 items-center rounded-full border border-transparent bg-error/10 px-4 text-[12.5px] font-semibold text-error">
              {t("blacklist.matches.count", { count: data.all_total })}
            </span>
            {canUnblockAll && (
              <Button
                variant="secondary"
                onClick={() => setIsUnblockConfirmOpen(true)}
              >
                <Unlock className="size-3.5" />
                {t("blacklist.matches.unblockAll.button")}
              </Button>
            )}
          </div>
        )
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {data !== null && data.all_total === 0 && (
        <EmptyState text={t("blacklist.matches.empty")} />
      )}

      {data !== null && data.all_total > 0 && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <SearchField
              id="blacklist-matches-search"
              label={t("blacklist.matches.searchPlaceholder")}
              hideLabel
              placeholder={t("blacklist.matches.searchPlaceholder")}
              value={search}
              onChange={(value) => {
                setSearch(value);
                setPage(1);
              }}
            />
            <div className="w-full sm:w-64">
              <PillTabs
                items={(
                  [
                    ["ALL", t("blacklist.matches.allOrigins")],
                    ["manual", t("blacklist.matches.manualOrigin")],
                    ["lists", t("blacklist.matches.listsOrigin")],
                  ] as const
                ).map(([key, label]) => ({ key, label }))}
                activeKey={origin ?? "ALL"}
                onSelect={(key) => changeOrigin(key === "ALL" ? undefined : key)}
                size="field"
              />
            </div>
          </div>

          <div className="-mx-2 mt-2 -mb-1 overflow-x-auto px-2 py-1">
            <table className="w-full min-w-[640px] border-separate border-spacing-0 text-[13px]">
              <thead>
                <tr className={`text-left ${EYEBROW_CLASS} [&>th]:border-b [&>th]:border-border`}>
                  <th scope="col" className="px-3 py-2 font-semibold">{t("blacklist.matches.columnUser")}</th>
                  <th scope="col" className="px-3 py-2 font-semibold">{t("blacklist.matches.columnHit")}</th>
                  <th scope="col" className="px-3 py-2 font-semibold">{t("blacklist.matches.columnOrigin")}</th>
                  <th scope="col" className="px-3 py-2 font-semibold">{t("blacklist.matches.columnStatus")}</th>
                  <th scope="col" className="w-10 px-3 py-2">
                    <span className="sr-only">{t("blacklist.matches.openUser")}</span>
                  </th>
                </tr>
                <tr className="h-1" />
              </thead>
              <tbody className="[&>tr:not(:last-child)>td]:border-b [&>tr:not(:last-child)>td]:border-border/50">
                {data.items.map((match) => (
                  <motion.tr
                    key={match.user.id}
                    onClick={() => setDetailsUser(match.user)}
                    className="cursor-pointer [&>td]:transition-colors hover:[&>td]:bg-white/[0.04] [&>td:first-child]:rounded-l-full [&>td:last-child]:rounded-r-full"
                  >
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground">
                          {initials(match.user.name)}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-foreground">{match.user.name}</p>
                          <p className="truncate text-[12px] text-muted-foreground">
                            {match.user.username ? `@${match.user.username}` : `#${match.user.id}`}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col gap-1">
                        {match.hits.map((hit) => (
                          <div key={hit.kind} className="flex items-center gap-2">
                            <KindBadge
                              kind={hit.kind}
                              label={
                                hit.kind === "TELEGRAM_ID"
                                  ? t("blacklist.manual.kindTelegramId")
                                  : t("blacklist.manual.kindEmail")
                              }
                            />
                            <span className="truncate font-mono text-[12.5px] text-foreground">{hit.value}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-foreground/80">
                      {matchOrigins(match).map(originLabel).join(", ")}
                    </td>
                    <td className="px-3 py-2">
                      {match.user.is_blocked ? (
                        <span className="inline-flex rounded-full bg-error/10 px-2.5 py-0.5 text-[12px] font-semibold text-error">
                          {t("blacklist.matches.blocked")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-0.5 text-[12px] font-semibold text-warning">
                          {t("blacklist.matches.pending")}
                          <FieldHint text={t("blacklist.matches.pendingHint")} />
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <IconButton size="8"
                        onClick={() => setDetailsUser(match.user)}
                      >
                        <ChevronRight className="size-4" />
                      </IconButton>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
            {data.total === 0 && (
              <EmptyState icon={SearchX} text={t("blacklist.matches.noResults")} />
            )}
          </div>

          {pageCount > 1 && (
            <div className="mt-3 flex items-center justify-between gap-3 px-3">
              <span className="text-[12.5px] tabular-nums text-muted-foreground">
                {t("blacklist.matches.range", {
                  from: (page - 1) * PAGE_SIZE + 1,
                  to: (page - 1) * PAGE_SIZE + data.items.length,
                  total: data.total,
                })}
              </span>
              <div className="flex gap-1.5">
                <Pressable
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                  className="flex size-8 items-center justify-center rounded-full border border-border text-foreground transition-colors hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronLeft className="size-4" />
                </Pressable>
                <Pressable
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= pageCount}
                  className="flex size-8 items-center justify-center rounded-full border border-border text-foreground transition-colors hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronRight className="size-4" />
                </Pressable>
              </div>
            </div>
          )}
        </>
      )}

      {isUnblockConfirmOpen && (
        <ConfirmDialog
          title={t("blacklist.matches.unblockAll.title")}
          message={t("blacklist.matches.unblockAll.confirm")}
          confirmLabel={t("blacklist.matches.unblockAll.button")}
          cancelLabel={t("common.cancel")}
          danger
          size="md"
          onConfirm={() => {
            void handleUnblockAll();
            setIsUnblockConfirmOpen(false);
          }}
          onCancel={() => setIsUnblockConfirmOpen(false)}
        />
      )}
      {detailsUser && <UserDetailsDialog user={detailsUser} onClose={() => setDetailsUser(null)} />}
    </BlacklistCard>
  );
}
