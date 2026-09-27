import { AlertTriangle, Ban, Globe, Inbox, Plus, RefreshCw, Search, Trash2, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  addBlacklistEntry,
  addBlacklistSource,
  getBlacklist,
  listBlacklistSources,
  removeBlacklistEntry,
  removeBlacklistSource,
  syncBlacklistSources,
  toggleBlacklistSource,
  type Blacklist,
  type BlacklistKind,
  type BlacklistSource,
} from "@entities/blacklist/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PillTabs } from "@features/dialog-canvas-editor/PillTabs";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

import { BlacklistCard, KindBadge, inputClassName } from "./BlacklistCard";
import { BlacklistMatchesCard } from "./BlacklistMatchesCard";

// Sync is fire-and-forget on the backend -- give it a moment to finish before
// refetching the source list so entries_count/last_synced_at have a chance
// to update. Not a guarantee of completion, just a reasonable delay.
const SYNC_REFRESH_DELAY_MS = 1500;
const ENTRIES_PREVIEW_LIMIT = 8;

type EntryFilter = "ALL" | BlacklistKind;

interface BlacklistEntryRow {
  kind: BlacklistKind;
  value: string;
}

// anything with "@" is an email; the rest goes in as a Telegram ID (backend keeps the digits)
function detectKind(value: string): BlacklistKind {
  return value.includes("@") ? "EMAIL" : "TELEGRAM_ID";
}

// same box as inputClassName (1px border + py-2 + 20px line) so it lines up with the field beside it
const primaryButtonClassName =
  "flex shrink-0 items-center gap-1.5 rounded-full border border-transparent bg-accent px-3.5 py-2 text-[12.5px] leading-5 font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50";
const iconButtonClassName =
  "flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error";

export function BlacklistPage() {
  const currentUserState = useCurrentUser();
  if (currentUserState.kind !== "ready") return <Spinner />;
  // mounted only once permissions are known -- the fetchers below are chosen by them once
  return <BlacklistContent permissions={currentUserState.data.effective_permissions} />;
}

function BlacklistContent({ permissions }: { permissions: Permission[] }) {
  const canViewSources = permissions.includes("BLACKLIST_SOURCES_VIEW");
  const canViewMatches = permissions.includes("BLACKLIST_MATCHES_VIEW");

  const [blacklistState, reloadBlacklist, setBlacklist] = useAsyncResource(getBlacklist);
  const [sourcesState, reloadSources, setSources] = useAsyncResource((signal) =>
    canViewSources ? listBlacklistSources(signal) : Promise.resolve([]),
  );
  const [matchesReloadKey, setMatchesReloadKey] = useState(0);
  const reloadMatches = () => setMatchesReloadKey((key) => key + 1);

  const handleBlacklistChanged = (data: Blacklist) => {
    setBlacklist(data);
    reloadMatches();
  };

  const handleSynced = () => {
    reloadBlacklist();
    reloadSources();
    reloadMatches();
  };

  return (
    <div className="flex flex-col gap-4">
      {canViewSources && (
        <BlacklistSourcesCard
          state={sourcesState}
          setSources={setSources}
          permissions={permissions}
          onSynced={handleSynced}
        />
      )}
      <ManualEntriesCard state={blacklistState} permissions={permissions} onChanged={handleBlacklistChanged} />
      {canViewMatches && (
        <BlacklistMatchesCard
          reloadKey={matchesReloadKey}
          canUnblockAll={permissions.includes("USERS_UNBLOCK_BLACKLIST_MATCHES")}
          onUnblocked={() => {
            reloadBlacklist();
            reloadMatches();
          }}
        />
      )}
    </div>
  );
}

interface ManualEntriesCardProps {
  state: AsyncState<Blacklist>;
  permissions: Permission[];
  onChanged: (data: Blacklist) => void;
}

function ManualEntriesCard({ state, permissions, onChanged }: ManualEntriesCardProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const [entryValue, setEntryValue] = useState("");
  const [isAddingEntry, setIsAddingEntry] = useState(false);
  const [filter, setFilter] = useState<EntryFilter>("ALL");
  const [search, setSearch] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);

  const kindLabel = (kind: BlacklistKind) =>
    kind === "TELEGRAM_ID" ? t("blacklist.manual.kindTelegramId") : t("blacklist.manual.kindEmail");

  const rows: BlacklistEntryRow[] =
    state.kind === "ready"
      ? [
          ...state.data.telegram_ids.map((value) => ({ kind: "TELEGRAM_ID" as const, value: String(value) })),
          ...state.data.emails.map((value) => ({ kind: "EMAIL" as const, value })),
        ]
      : [];
  const query = search.trim().toLowerCase();
  const filtered = rows.filter(
    (row) => (filter === "ALL" || row.kind === filter) && (!query || row.value.toLowerCase().includes(query)),
  );
  const visible = isExpanded ? filtered : filtered.slice(0, ENTRIES_PREVIEW_LIMIT);
  const hiddenCount = filtered.length - visible.length;

  const handleAddEntry = async () => {
    const value = entryValue.trim();
    if (!value) return;
    setIsAddingEntry(true);
    try {
      onChanged(await addBlacklistEntry(detectKind(value), value));
      setEntryValue("");
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.manual.addError")));
    } finally {
      setIsAddingEntry(false);
    }
  };

  const handleRemoveEntry = async (row: BlacklistEntryRow) => {
    try {
      onChanged(await removeBlacklistEntry(row.kind, row.value));
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.manual.removeError")));
    }
  };

  return (
    <BlacklistCard icon={Ban} title={t("blacklist.manual.title")} description={t("blacklist.manual.description")}>
      {permissions.includes("BLACKLIST_ENTRY_ADD") && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void handleAddEntry();
          }}
          className="mt-4 flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3"
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={entryValue}
              onChange={(event) => setEntryValue(event.target.value)}
              placeholder={t("blacklist.manual.valuePlaceholder")}
              aria-label={t("blacklist.manual.valueLabel")}
              className={`${inputClassName} flex-1`}
            />
            <motion.button
              type="submit"
              disabled={isAddingEntry || !entryValue.trim()}
              {...bounceTap(bounceStrength)}
              className={primaryButtonClassName}
            >
              <Plus className="size-3.5" />
              {t("blacklist.manual.add")}
            </motion.button>
          </div>
        </form>
      )}

      {state.kind === "loading" && <Spinner className="mt-4" />}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("blacklist.manual.loadError")}</p>}
      {state.kind === "ready" && rows.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
          <Inbox className="size-5" />
          <p className="text-sm">{t("blacklist.manual.empty")}</p>
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="relative min-w-40 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("blacklist.manual.searchPlaceholder")}
                aria-label={t("blacklist.manual.searchPlaceholder")}
                className="w-full rounded-xl border border-border bg-input/60 py-2 pl-9 pr-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </div>
            <div className="w-full sm:w-64">
              <PillTabs
                items={(["ALL", "TELEGRAM_ID", "EMAIL"] as const).map((kind) => ({
                  key: kind,
                  label: (
                    <>
                      {kind === "ALL" ? t("blacklist.manual.filterAll") : kindLabel(kind)}{" "}
                      <span className="text-[11.5px] tabular-nums opacity-70">
                        {kind === "ALL" ? rows.length : rows.filter((row) => row.kind === kind).length}
                      </span>
                    </>
                  ),
                }))}
                activeKey={filter}
                onSelect={setFilter}
              />
            </div>
          </div>

          <ul className="mt-2 flex flex-col divide-y divide-border/50">
            {visible.map((row) => (
              <li
                key={`${row.kind}:${row.value}`}
                className="flex items-center gap-2.5 rounded-full py-1.5 pl-3 pr-1.5 transition-colors hover:bg-white/[0.04]"
              >
                <KindBadge kind={row.kind} label={kindLabel(row.kind)} />
                <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-foreground">{row.value}</span>
                {permissions.includes("BLACKLIST_ENTRY_REMOVE") && (
                  <button
                    type="button"
                    onClick={() => void handleRemoveEntry(row)}
                    aria-label={t("blacklist.manual.remove")}
                    className={iconButtonClassName}
                  >
                    <X className="size-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
          {filtered.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("blacklist.manual.noResults")}</p>
          )}
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setIsExpanded(true)}
              className="mt-2 w-full rounded-full border border-dashed border-border py-2 text-[12.5px] font-medium text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
            >
              {t("blacklist.manual.showMore", { count: hiddenCount })}
            </button>
          )}
        </>
      )}
    </BlacklistCard>
  );
}

interface BlacklistSourcesCardProps {
  state: AsyncState<BlacklistSource[]>;
  setSources: (sources: BlacklistSource[]) => void;
  permissions: Permission[];
  onSynced: () => void;
}

function BlacklistSourcesCard({ state, setSources, permissions, onSynced }: BlacklistSourcesCardProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [isAddingSource, setIsAddingSource] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingRemoveSource, setPendingRemoveSource] = useState<BlacklistSource | null>(null);

  const sources = state.kind === "ready" ? state.data : [];

  const handleAddSource = async () => {
    const url = sourceUrl.trim();
    if (!url) return;
    setIsAddingSource(true);
    try {
      const created = await addBlacklistSource(url, sourceName.trim() || undefined);
      setSources(sources.concat(created));
      setSourceUrl("");
      setSourceName("");
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.addError")));
    } finally {
      setIsAddingSource(false);
    }
  };

  const handleRemoveSource = async (source: BlacklistSource) => {
    try {
      await removeBlacklistSource(source.id);
      setSources(sources.filter((s) => s.id !== source.id));
      onSynced();
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.removeError")));
    }
  };

  const handleToggleSource = async (source: BlacklistSource, enabled: boolean) => {
    try {
      const updated = await toggleBlacklistSource(source.id, enabled);
      setSources(sources.map((s) => (s.id === updated.id ? updated : s)));
      onSynced();
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.toggleError")));
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncBlacklistSources();
      toast.success(t("blacklist.sources.syncStarted"));
      setTimeout(onSynced, SYNC_REFRESH_DELAY_MS);
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.syncError")));
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <BlacklistCard
      icon={Globe}
      title={t("blacklist.sources.title")}
      description={t("blacklist.sources.description")}
      action={
        permissions.includes("BLACKLIST_SYNC") && (
          <motion.button
            type="button"
            onClick={() => void handleSync()}
            disabled={isSyncing}
            {...bounceTap(bounceStrength)}
            className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3.5 py-2 text-[12.5px] font-semibold text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 ${isSyncing ? "animate-spin" : ""}`} />
            {t("blacklist.sources.syncNow")}
          </motion.button>
        )
      }
    >
      {permissions.includes("BLACKLIST_SOURCE_ADD") && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void handleAddSource();
          }}
          className="mt-4 flex flex-col gap-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3"
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="blacklist-source-url" className="text-sm font-medium text-foreground/80">
              {t("blacklist.sources.urlLabel")}
            </label>
            <input
              id="blacklist-source-url"
              type="url"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              placeholder={t("blacklist.sources.urlPlaceholder")}
              className={inputClassName}
            />
          </div>
          <div className="flex items-end gap-2">
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <label htmlFor="blacklist-source-name" className="text-sm font-medium text-foreground/80">
                {t("blacklist.sources.nameLabel")}
              </label>
              <input
                id="blacklist-source-name"
                type="text"
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                placeholder={t("blacklist.sources.namePlaceholder")}
                className={inputClassName}
              />
            </div>
            <motion.button
              type="submit"
              disabled={isAddingSource || !sourceUrl.trim()}
              {...bounceTap(bounceStrength)}
              className={primaryButtonClassName}
            >
              <Plus className="size-3.5" />
              {t("blacklist.sources.add")}
            </motion.button>
          </div>
        </form>
      )}

      {state.kind === "loading" && <Spinner className="mt-4" />}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("blacklist.sources.loadError")}</p>}
      {state.kind === "ready" && sources.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
          <Inbox className="size-5" />
          <p className="text-sm">{t("blacklist.sources.empty")}</p>
        </div>
      )}

      {sources.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2">
          {sources.map((source) => (
            <li
              key={source.id}
              className={`rounded-xl bg-white/[0.03] p-3 transition-opacity ${source.enabled ? "" : "opacity-60"}`}
            >
              <div className="flex items-start gap-3">
                <span
                  aria-hidden
                  className={`mt-1.5 size-2 shrink-0 rounded-full ${
                    !source.enabled ? "bg-muted-foreground" : source.last_error ? "bg-warning" : "bg-success"
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold text-foreground">{source.name ?? source.url}</p>
                  {source.name && (
                    <p className="truncate font-mono text-[12px] text-muted-foreground">{source.url}</p>
                  )}
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums text-foreground/80">
                      {t("blacklist.sources.entriesCount", { count: source.entries_count })}
                    </span>
                    <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11.5px] text-muted-foreground">
                      {source.last_synced_at
                        ? t("blacklist.sources.lastSynced", {
                            date: new Date(source.last_synced_at).toLocaleString(),
                          })
                        : t("blacklist.sources.neverSynced")}
                    </span>
                  </div>
                </div>
                {permissions.includes("BLACKLIST_SOURCE_TOGGLE") && (
                  <Switch
                    checked={source.enabled}
                    onChange={(checked) => void handleToggleSource(source, checked)}
                    ariaLabel={t("blacklist.sources.enabled")}
                  />
                )}
                {permissions.includes("BLACKLIST_SOURCE_REMOVE") && (
                  <button
                    type="button"
                    onClick={() => setPendingRemoveSource(source)}
                    aria-label={t("blacklist.sources.remove")}
                    className={`${iconButtonClassName} -mt-1`}
                  >
                    <Trash2 className="size-4" />
                  </button>
                )}
              </div>
              {source.last_error && (
                <div className="mt-2.5 flex items-center gap-1.5 rounded-full bg-warning/10 px-3 py-1.5 text-[12px] text-warning">
                  <AlertTriangle className="size-3.5 shrink-0" />
                  <span className="truncate">{source.last_error}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {pendingRemoveSource && (
        <ConfirmDialog
          title={t("blacklist.sources.remove")}
          message={t("blacklist.sources.removeConfirm", {
            name: pendingRemoveSource.name ?? pendingRemoveSource.url,
          })}
          confirmLabel={t("blacklist.sources.removeConfirmButton")}
          cancelLabel={t("blacklist.sources.removeCancelButton")}
          danger
          onConfirm={() => {
            void handleRemoveSource(pendingRemoveSource);
            setPendingRemoveSource(null);
          }}
          onCancel={() => setPendingRemoveSource(null)}
        />
      )}
    </BlacklistCard>
  );
}
