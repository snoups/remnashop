import { AlertTriangle, Ban, Globe, Loader2, Plus, RefreshCw, SearchX, Trash2, X } from "lucide-react";
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
  updateBlacklistSource,
  type Blacklist,
  type BlacklistKind,
  type BlacklistSource,
} from "@entities/blacklist/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PillTabs } from "@shared/ui/PillTabs";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { IconButton } from "@shared/ui/IconButton";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { Tag } from "@shared/ui/Tag";
import { TextInput } from "@shared/ui/TextInput";
import { SearchField } from "@shared/ui/SearchField";
import { Field } from "@shared/ui/Field";
import { LIST_BODY_CLASS } from "@shared/ui/classes";
import { formatDateTime } from "@shared/lib/relative-time";

import { BlacklistCard, KindBadge } from "./BlacklistCard";
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

const EMAIL_RE = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

// mirrors backend blacklist/normalize.py's normalize_identity
function isValidEntry(value: string): boolean {
  if (detectKind(value) === "EMAIL") return EMAIL_RE.test(value);
  return value.replace(/\D+/g, "").replace(/^0+/, "") !== "";
}

export function BlacklistPage() {
  const currentUserState = useCurrentUser();
  if (currentUserState.kind !== "ready") return <Spinner size="page" />;
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

  const trimmedEntry = entryValue.trim();
  const isEntryInvalid = trimmedEntry !== "" && !isValidEntry(trimmedEntry);

  const handleAddEntry = async () => {
    const value = entryValue.trim();
    if (!value || !isValidEntry(value)) return;
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

  const [removingKey, setRemovingKey] = useState<string | null>(null);

  const handleRemoveEntry = async (row: BlacklistEntryRow) => {
    setRemovingKey(`${row.kind}:${row.value}`);
    try {
      onChanged(await removeBlacklistEntry(row.kind, row.value));
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.manual.removeError")));
    } finally {
      setRemovingKey(null);
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
            <TextInput
              type="text"
              value={entryValue}
              onChange={(event) => setEntryValue(event.target.value)}
              placeholder={t("blacklist.manual.valuePlaceholder")}
              aria-invalid={isEntryInvalid}
              className="min-w-0 flex-1"
            />
            <Button
              variant="accent"
              size="field"
              type="submit"
              disabled={isAddingEntry || !trimmedEntry || isEntryInvalid}
            >
              <Plus className="size-3.5" />
              {t("common.add")}
            </Button>
          </div>
          {isEntryInvalid && (
            <p id="blacklist-entry-error" className="-mt-1 text-[12px] text-error">
              {t("blacklist.manual.valueInvalid")}
            </p>
          )}
        </form>
      )}

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("blacklist.manual.loadError")}</p>}
      {state.kind === "ready" && rows.length === 0 && (
        <EmptyState text={t("blacklist.manual.empty")} />
      )}

      {rows.length > 0 && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <SearchField
              id="blacklist-search"
              label={t("blacklist.manual.searchPlaceholder")}
              hideLabel
              placeholder={t("blacklist.manual.searchPlaceholder")}
              value={search}
              onChange={setSearch}
            />
            <div className="w-full sm:w-64">
              <PillTabs
                items={(["ALL", "TELEGRAM_ID", "EMAIL"] as const).map((kind) => ({
                  key: kind,
                  label: kind === "ALL" ? t("blacklist.manual.filterAll") : kindLabel(kind),
                }))}
                activeKey={filter}
                onSelect={setFilter}
                size="field"
              />
            </div>
          </div>

          <ul className={`mt-2 ${LIST_BODY_CLASS}`}>
            {visible.map((row) => (
              <li
                key={`${row.kind}:${row.value}`}
                className="flex items-center gap-2.5 rounded-full py-1.5 pl-3 pr-1.5 transition-colors hover:bg-white/[0.04]"
              >
                <KindBadge kind={row.kind} label={kindLabel(row.kind)} />
                <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-foreground">{row.value}</span>
                {permissions.includes("BLACKLIST_ENTRY_REMOVE") && (
                  <IconButton
                    size="8"
                    tone="danger"
                    onClick={() => void handleRemoveEntry(row)}
                    disabled={removingKey !== null}
                  >
                    {removingKey === `${row.kind}:${row.value}` ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <X className="size-4" />
                    )}
                  </IconButton>
                )}
              </li>
            ))}
          </ul>
          {filtered.length === 0 && (
            <EmptyState icon={SearchX} text={t("blacklist.manual.noResults")} />
          )}
          {hiddenCount > 0 && (
            <LoadMoreButton
              onClick={() => setIsExpanded(true)}
              shown={visible.length}
              total={filtered.length}
              className="mt-2"
            />
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
  const { t, i18n } = useTranslation();

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
      const updated = await updateBlacklistSource(source.id, enabled);
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
          <Button
            variant="secondary"
            onClick={() => void handleSync()}
            disabled={isSyncing}
          >
            <RefreshCw className={`size-3.5 ${isSyncing ? "animate-spin" : ""}`} />
            {t("blacklist.sources.syncNow")}
          </Button>
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
          <Field label={t("blacklist.sources.urlLabel")} htmlFor="blacklist-source-url" aside={<span className="text-error">*</span>}>
            <TextInput
              id="blacklist-source-url"
              type="url"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              placeholder={t("blacklist.sources.urlPlaceholder")}
              className="min-w-0"
            />
          </Field>
          <div className="flex items-end gap-2">
            <Field label={t("blacklist.sources.nameLabel")} htmlFor="blacklist-source-name" className="min-w-0 flex-1">
              <TextInput
                id="blacklist-source-name"
                type="text"
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                placeholder={t("blacklist.sources.namePlaceholder")}
                className="min-w-0"
              />
            </Field>
            <Button
              variant="accent"
              size="field"
              type="submit"
              disabled={isAddingSource || !sourceUrl.trim()}
            >
              <Plus className="size-3.5" />
              {t("blacklist.sources.add")}
            </Button>
          </div>
        </form>
      )}

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("blacklist.sources.loadError")}</p>}
      {state.kind === "ready" && sources.length === 0 && (
        <EmptyState text={t("blacklist.sources.empty")} />
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
                    <Tag>
                      {t("blacklist.sources.entriesCount", { count: source.entries_count })}
                    </Tag>
                    <Tag>
                      {source.last_synced_at
                        ? t("blacklist.sources.lastSynced", {
                            date: formatDateTime(source.last_synced_at, i18n.language),
                          })
                        : t("blacklist.sources.neverSynced")}
                    </Tag>
                  </div>
                </div>
                {permissions.includes("BLACKLIST_SOURCE_UPDATE") && (
                  <Switch
                    checked={source.enabled}
                    onChange={(checked) => void handleToggleSource(source, checked)}
                  />
                )}
                {permissions.includes("BLACKLIST_SOURCE_REMOVE") && (
                  <IconButton
                    size="8"
                    tone="danger"
                    onClick={() => setPendingRemoveSource(source)}
                    className="-mt-1"
                  >
                    <Trash2 className="size-4" />
                  </IconButton>
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
          title={t("blacklist.sources.removeConfirmTitle")}
          message={t("blacklist.sources.removeConfirm", {
            name: pendingRemoveSource.name ?? pendingRemoveSource.url,
          })}
          confirmLabel={t("blacklist.sources.removeConfirmButton")}
          cancelLabel={t("common.cancel")}
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
