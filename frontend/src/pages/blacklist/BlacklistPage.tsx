import { Ban, Globe, Loader2, Mail, Plus, RefreshCw, SearchX, Trash2, X } from "lucide-react";
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
import { Badge } from "@shared/ui/Badge";
import { TelegramIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { FieldHint } from "@shared/ui/FieldHint";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { Spinner } from "@shared/ui/Spinner";
import { formatDateTime } from "@shared/lib/relative-time";

import { BlacklistCard } from "./BlacklistCard";
import { BlacklistMatchesCard } from "./BlacklistMatchesCard";

// Sync is fire-and-forget on the backend; refetching after a short delay
// usually catches the new entries_count/last_synced_at.
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
  // mounted once permissions are known, since they pick the fetchers below
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
    <div className="flex flex-col gap-5">
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
  const canAdd = permissions.includes("BLACKLIST_ENTRY_ADD");

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
      {canAdd && (
        <SectionFields>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleAddEntry();
            }}
            className="flex flex-col gap-1.5"
          >
            <div className="flex min-w-0 gap-2">
              <Input
                className="flex-1"
                value={entryValue}
                onChange={(event) => setEntryValue(event.target.value)}
                placeholder={t("blacklist.manual.valuePlaceholder")}
                aria-invalid={isEntryInvalid}
              />
              <Button
                variant="glassAccent"
                type="submit"
                icon={Plus}
                isLoading={isAddingEntry}
                disabled={!trimmedEntry || isEntryInvalid}
              >
                {t("common.add")}
              </Button>
            </div>
            {isEntryInvalid && <p className="text-[12px] text-error">{t("blacklist.manual.valueInvalid")}</p>}
          </form>
        </SectionFields>
      )}

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && rows.length === 0 && (
        <EmptyState text={t("blacklist.manual.empty")} />
      )}

      {rows.length > 0 && (
        <>
          <SectionFields divided={canAdd}>
            <div className="flex flex-wrap items-center gap-2">
              <SearchField
                id="blacklist-search"
                label={t("blacklist.manual.searchPlaceholder")}
                hideLabel
                compact
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
                />
              </div>
            </div>
          </SectionFields>

          <SectionRows flush>
            {visible.map((row) => (
              <Row
                key={`${row.kind}:${row.value}`}
                icon={row.kind === "TELEGRAM_ID" ? TelegramIcon : Mail}
                label={<span className="min-w-0 truncate font-mono">{row.value}</span>}
                description={kindLabel(row.kind)}
              >
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
              </Row>
            ))}
          </SectionRows>
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
  const canAddSource = permissions.includes("BLACKLIST_SOURCE_ADD");

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
          <Button variant="glass" icon={RefreshCw} onClick={() => void handleSync()} isLoading={isSyncing}>
            {t("blacklist.sources.syncNow")}
          </Button>
        )
      }
    >
      {canAddSource && (
        <SectionFields>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleAddSource();
            }}
            className="flex flex-col gap-3"
          >
            <Field label={t("blacklist.sources.urlLabel")} htmlFor="blacklist-source-url" required>
              <Input
                id="blacklist-source-url"
                type="url"
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder={t("blacklist.sources.urlPlaceholder")}
              />
            </Field>
            <div className="flex items-end gap-2">
              <div className="min-w-0 flex-1">
                <Field label={t("blacklist.sources.nameLabel")} htmlFor="blacklist-source-name">
                  <Input
                    id="blacklist-source-name"
                    value={sourceName}
                    onChange={(event) => setSourceName(event.target.value)}
                    placeholder={t("blacklist.sources.namePlaceholder")}
                  />
                </Field>
              </div>
              <Button
                variant="glassAccent"
                type="submit"
                icon={Plus}
                isLoading={isAddingSource}
                disabled={!sourceUrl.trim()}
              >
                {t("common.add")}
              </Button>
            </div>
          </form>
        </SectionFields>
      )}

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && sources.length === 0 && (
        <EmptyState text={t("blacklist.sources.empty")} />
      )}

      {sources.length > 0 && (
        <SectionRows divided={canAddSource}>
          {sources.map((source) => (
            <div key={source.id} className={`transition-opacity ${source.enabled ? "" : "opacity-60"}`}>
              <Row
                icon={Globe}
                label={
                  <>
                    <FieldHint
                      text={source.url}
                      content={<span className="break-all">{source.url}</span>}
                      side="bottom"
                      glass
                      className="min-w-0"
                      trigger={<span className="min-w-0 cursor-help truncate">{source.name ?? source.url}</span>}
                    />
                    {source.last_error && (
                      <FieldHint
                        text={source.last_error}
                        side="bottom"
                        error
                        trigger={
                          <Badge borderless tone="error" className="cursor-help">
                            {t("blacklist.sources.errorBadge")}
                          </Badge>
                        }
                      />
                    )}
                  </>
                }
                description={
                  <p className="truncate">
                    {t("blacklist.sources.entriesCount", { count: source.entries_count })}
                    {" · "}
                    {source.last_synced_at
                      ? t("blacklist.sources.lastSynced", {
                          date: formatDateTime(source.last_synced_at, i18n.language),
                        })
                      : t("blacklist.sources.neverSynced")}
                  </p>
                }
              >
                {permissions.includes("BLACKLIST_SOURCE_REMOVE") && (
                  <IconButton size="8" tone="danger" onClick={() => setPendingRemoveSource(source)}>
                    <Trash2 className="size-4" />
                  </IconButton>
                )}
                {permissions.includes("BLACKLIST_SOURCE_UPDATE") && (
                  <Switch checked={source.enabled} onChange={(checked) => void handleToggleSource(source, checked)} />
                )}
              </Row>
            </div>
          ))}
        </SectionRows>
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
