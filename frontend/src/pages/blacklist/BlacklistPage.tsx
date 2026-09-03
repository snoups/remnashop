import { AlertTriangle, Ban, Globe, Plus, RefreshCw, X } from "lucide-react";
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
  type BlacklistKind,
  type BlacklistSource,
} from "@entities/blacklist/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

// Sync is fire-and-forget on the backend -- give it a moment to finish before
// refetching the source list so entries_count/last_synced_at have a chance
// to update. Not a guarantee of completion, just a reasonable delay.
const SYNC_REFRESH_DELAY_MS = 1500;

interface BlacklistEntryRow {
  kind: BlacklistKind;
  value: string;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

export function BlacklistPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];

  const [blacklistState, reloadBlacklist, setBlacklist] = useAsyncResource(getBlacklist);

  const [entryKind, setEntryKind] = useState<BlacklistKind>("TELEGRAM_ID");
  const [entryValue, setEntryValue] = useState("");
  const [isAddingEntry, setIsAddingEntry] = useState(false);

  const rows: BlacklistEntryRow[] =
    blacklistState.kind === "ready"
      ? [
          ...blacklistState.data.telegram_ids.map((value) => ({
            kind: "TELEGRAM_ID" as const,
            value: String(value),
          })),
          ...blacklistState.data.emails.map((value) => ({ kind: "EMAIL" as const, value })),
        ]
      : [];

  const handleAddEntry = async () => {
    const value = entryValue.trim();
    if (!value) return;
    setIsAddingEntry(true);
    try {
      const result = await addBlacklistEntry(entryKind, value);
      setBlacklist(result);
      setEntryValue("");
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.manual.addError")));
    } finally {
      setIsAddingEntry(false);
    }
  };

  const handleRemoveEntry = async (row: BlacklistEntryRow) => {
    try {
      const result = await removeBlacklistEntry(row.kind, row.value);
      setBlacklist(result);
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.manual.removeError")));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Ban className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("blacklist.manual.title")}</h2>
            <p className="text-[12.5px] text-muted-foreground">{t("blacklist.manual.description")}</p>
          </div>
        </div>

        {permissions.includes("BLACKLIST_ENTRY_ADD") && (
          <div className="mt-4 flex flex-wrap items-end gap-2">
            <div className="w-40">
              <SelectDropdown
                value={entryKind}
                onChange={(value) => setEntryKind(value as BlacklistKind)}
                icon={Ban}
                placeholder={t("blacklist.manual.kind")}
                options={[
                  { value: "TELEGRAM_ID", label: t("blacklist.manual.kindTelegramId") },
                  { value: "EMAIL", label: t("blacklist.manual.kindEmail") },
                ]}
              />
            </div>
            <input
              type="text"
              value={entryValue}
              onChange={(event) => setEntryValue(event.target.value)}
              placeholder={t("blacklist.manual.valuePlaceholder")}
              className={`${fieldClassName} min-w-48 flex-1`}
            />
            <motion.button
              type="button"
              onClick={() => void handleAddEntry()}
              disabled={isAddingEntry || !entryValue.trim()}
              {...bounceTap(bounceStrength)}
              className="flex shrink-0 items-center gap-1.5 rounded-full bg-accent px-3.5 py-2 text-[12.5px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="size-3.5" />
              {t("blacklist.manual.add")}
            </motion.button>
          </div>
        )}

        <div className="mt-3">
          {blacklistState.kind === "loading" && (
            <p className="text-sm text-muted-foreground">{t("blacklist.loading")}</p>
          )}
          {blacklistState.kind === "error" && (
            <p className="text-sm text-error">{t("blacklist.manual.loadError")}</p>
          )}
          {blacklistState.kind === "ready" && rows.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("blacklist.manual.empty")}</p>
          )}
          {blacklistState.kind === "ready" && rows.length > 0 && (
            <div className="flex flex-col">
              {rows.map((row) => (
                <div
                  key={`${row.kind}:${row.value}`}
                  className="flex items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {row.kind === "TELEGRAM_ID"
                        ? t("blacklist.manual.kindTelegramId")
                        : t("blacklist.manual.kindEmail")}
                    </span>
                    <span className="font-mono text-[13px] text-foreground">{row.value}</span>
                  </div>
                  {permissions.includes("BLACKLIST_ENTRY_REMOVE") && (
                    <button
                      type="button"
                      onClick={() => void handleRemoveEntry(row)}
                      aria-label={t("blacklist.manual.remove")}
                      title={t("blacklist.manual.remove")}
                      className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error"
                    >
                      <X className="size-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {permissions.includes("BLACKLIST_SOURCES_VIEW") && (
        <BlacklistSourcesSection permissions={permissions} onSynced={reloadBlacklist} />
      )}
    </div>
  );
}

interface BlacklistSourcesSectionProps {
  permissions: Permission[];
  onSynced: () => void;
}

// Own component so listBlacklistSources() is never called without
// BLACKLIST_SOURCES_VIEW -- the page mounts this only when the permission is there.
function BlacklistSourcesSection({ permissions, onSynced }: BlacklistSourcesSectionProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const [sourcesState, reloadSources, setSources] = useAsyncResource(listBlacklistSources);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [isAddingSource, setIsAddingSource] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleAddSource = async () => {
    const url = sourceUrl.trim();
    if (!url) return;
    setIsAddingSource(true);
    try {
      const created = await addBlacklistSource(url, sourceName.trim() || undefined);
      setSources((sourcesState.kind === "ready" ? sourcesState.data : []).concat(created));
      setSourceUrl("");
      setSourceName("");
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.addError")));
    } finally {
      setIsAddingSource(false);
    }
  };

  const handleRemoveSource = async (source: BlacklistSource) => {
    if (!window.confirm(t("blacklist.sources.removeConfirm", { url: source.url }))) return;
    try {
      await removeBlacklistSource(source.id);
      setSources((sourcesState.kind === "ready" ? sourcesState.data : []).filter((s) => s.id !== source.id));
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.removeError")));
    }
  };

  const handleToggleSource = async (source: BlacklistSource, enabled: boolean) => {
    try {
      const updated = await toggleBlacklistSource(source.id, enabled);
      setSources(
        (sourcesState.kind === "ready" ? sourcesState.data : []).map((s) =>
          s.id === updated.id ? updated : s,
        ),
      );
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.toggleError")));
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncBlacklistSources();
      toast.success(t("blacklist.sources.syncStarted"));
      setTimeout(() => {
        reloadSources();
        onSynced();
      }, SYNC_REFRESH_DELAY_MS);
    } catch (err) {
      toast.error(getErrorMessage(err, t("blacklist.sources.syncError")));
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <div className="flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Globe className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("blacklist.sources.title")}</h2>
            <p className="text-[12.5px] text-muted-foreground">{t("blacklist.sources.description")}</p>
          </div>
        </div>
        {permissions.includes("BLACKLIST_SYNC") && (
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
        )}
      </div>

      {permissions.includes("BLACKLIST_SOURCE_ADD") && (
        <div className="mt-4 flex flex-wrap items-end gap-2">
          <input
            type="text"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder={t("blacklist.sources.urlPlaceholder")}
            className={`${fieldClassName} min-w-48 flex-1`}
          />
          <input
            type="text"
            value={sourceName}
            onChange={(event) => setSourceName(event.target.value)}
            placeholder={t("blacklist.sources.namePlaceholder")}
            className={`${fieldClassName} w-40`}
          />
          <motion.button
            type="button"
            onClick={() => void handleAddSource()}
            disabled={isAddingSource || !sourceUrl.trim()}
            {...bounceTap(bounceStrength)}
            className="flex shrink-0 items-center gap-1.5 rounded-full bg-accent px-3.5 py-2 text-[12.5px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="size-3.5" />
            {t("blacklist.sources.add")}
          </motion.button>
        </div>
      )}

      <div className="mt-3">
        {sourcesState.kind === "loading" && (
          <p className="text-sm text-muted-foreground">{t("blacklist.loading")}</p>
        )}
        {sourcesState.kind === "error" && (
          <p className="text-sm text-error">{t("blacklist.sources.loadError")}</p>
        )}
        {sourcesState.kind === "ready" && sourcesState.data.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("blacklist.sources.empty")}</p>
        )}
        {sourcesState.kind === "ready" && sourcesState.data.length > 0 && (
          <div className="flex flex-col divide-y divide-border/50">
            {sourcesState.data.map((source) => (
              <div key={source.id} className="flex flex-col gap-1.5 px-[12.5px] py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-foreground">
                      {source.name ?? source.url}
                    </p>
                    {source.name && (
                      <p className="truncate font-mono text-[12px] text-muted-foreground">{source.url}</p>
                    )}
                    <p className="text-[12px] text-muted-foreground">
                      {t("blacklist.sources.entriesCount", { count: source.entries_count })}
                      {" · "}
                      {source.last_synced_at
                        ? t("blacklist.sources.lastSynced", {
                            date: new Date(source.last_synced_at).toLocaleString(),
                          })
                        : t("blacklist.sources.neverSynced")}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
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
                        onClick={() => void handleRemoveSource(source)}
                        aria-label={t("blacklist.sources.remove")}
                        title={t("blacklist.sources.remove")}
                        className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error"
                      >
                        <X className="size-4" />
                      </button>
                    )}
                  </div>
                </div>
                {source.last_error && (
                  <div className="flex items-center gap-1.5 rounded-full bg-warning/10 px-3 py-1.5 text-[12px] text-warning">
                    <AlertTriangle className="size-3.5 shrink-0" />
                    <span className="truncate">{source.last_error}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
