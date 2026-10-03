import { useEffect, useRef, useState } from "react";

import { type BackupKind, type BackupRun, DEFAULT_PAGE_SIZE, listBackupRuns } from "@entities/backups/api";
import { usePaginatedList } from "@shared/lib/use-paginated-list";

export type RunsFilter = BackupKind | "ALL";

// plain polling, switch to SSE/websocket if the run list grows hot
const RUNS_POLL_INTERVAL_MS = 5000;
// the list endpoint caps page_size at 200
const RUNS_MAX_PAGE_SIZE = 200;

const kindFilter = (value: RunsFilter) => (value === "ALL" ? undefined : value);
const isActive = (run: BackupRun) => run.status === "PENDING" || run.status === "RUNNING";

/** The run history: paged, filtered by kind, polled so status changes show up without a reload. */
export function useBackupRuns(enabled: boolean, onRunsSettled: () => void) {
  const [filter, setFilterState] = useState<RunsFilter>("ALL");
  const { state, setState, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (value: RunsFilter, page, signal) =>
      enabled
        ? listBackupRuns({ kind: kindFilter(value), page, pageSize: DEFAULT_PAGE_SIZE }, signal)
        : Promise.resolve({ items: [], total: 0 }),
    filter,
  );

  const stateRef = useRef(state);
  stateRef.current = state;
  const onRunsSettledRef = useRef(onRunsSettled);
  onRunsSettledRef.current = onRunsSettled;

  // refetches every row already loaded, so status changes and new scheduled
  // runs show up without a reload; skipped while the tab is hidden
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const timer = setInterval(() => {
      const current = stateRef.current;
      if (document.hidden || current.kind !== "ready") return;
      const pageSize = Math.min(RUNS_MAX_PAGE_SIZE, Math.max(DEFAULT_PAGE_SIZE, current.items.length));
      listBackupRuns({ kind: kindFilter(filter), page: 1, pageSize })
        .then((result) => {
          if (cancelled) return;
          setState({ kind: "ready", items: result.items, total: result.total });
          if (current.items.some(isActive) && !result.items.some(isActive)) onRunsSettledRef.current();
        })
        .catch(() => {
          // next tick retries
        });
    }, RUNS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [filter, enabled, setState]);

  const setFilter = (value: RunsFilter) => {
    if (value === filter) return;
    setFilterState(value);
    setState({ kind: "loading" });
  };

  const prepend = (run: BackupRun) =>
    setState((prev) =>
      prev.kind === "ready" && (filter === "ALL" || filter === run.kind)
        ? { kind: "ready", items: [run, ...prev.items], total: prev.total + 1 }
        : prev,
    );

  const remove = (run: BackupRun) =>
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((item) => item.id !== run.id), total: prev.total - 1 }
        : prev,
    );

  return { state, filter, setFilter, isLoadingMore, hasMore, loadMore, prepend, remove };
}
