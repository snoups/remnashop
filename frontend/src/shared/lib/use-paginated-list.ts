import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";

import { useLoadGateHold } from "@shared/lib/load-gate";

export type PaginatedState<T> =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: T[]; total: number };

interface Page<T> {
  items: T[];
  total: number;
}

interface PaginatedList<T> {
  state: PaginatedState<T>;
  /** for local edits (an updated or deleted row) without a refetch */
  setState: Dispatch<SetStateAction<PaginatedState<T>>>;
  /** a refetch after a filter change is running; shown only past a short delay */
  isFetching: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  loadMore: () => Promise<void>;
  /** refetches page 1 as a filter change would, dropping the pages loaded past it */
  reload: () => void;
}

function defaultKey(item: unknown): unknown {
  return typeof item === "object" && item !== null && "id" in item ? item.id : undefined;
}

// most refetches resolve well under this, so typing in a filter doesn't flash the list dim on every pause
const FETCH_INDICATOR_DELAY_MS = 150;

/**
 * A "load more" list: refetches page 1 whenever `filters` changes (memoize it), appends later pages.
 * offset pagination drifts a row at a page boundary after local deletes; a keyset fetcher reads
 * its cursor from `loaded` (the rows on screen) and answers `total` as `loaded.length` + what's left.
 */
export function usePaginatedList<T, F>(
  fetchPage: (filters: F, page: number, signal?: AbortSignal, loaded?: T[]) => Promise<Page<T>>,
  filters: F,
  /** what makes a row unique, to drop repeats; a row without one is always kept */
  keyOf: (item: T) => unknown = defaultKey,
): PaginatedList<T> {
  const [state, setState] = useState<PaginatedState<T>>({ kind: "loading" });
  useLoadGateHold(state.kind === "loading");
  const [isFetching, setIsFetching] = useState(false);
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  // bumped on every page-1 load; a load-more started under an older value drops its
  // result instead of appending stale rows to a list that was already replaced
  const loadGenRef = useRef(0);
  const fetchPageRef = useRef(fetchPage);
  fetchPageRef.current = fetchPage;

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    fetchPageRef
      .current(filters, 1, controller.signal, [])
      .then((result) => {
        if (!controller.signal.aborted) setState({ kind: "ready", items: result.items, total: result.total });
      })
      .catch(() => {
        // keep what's on screen; the error state only replaces nothing
        if (!controller.signal.aborted) setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!controller.signal.aborted) setIsFetching(false);
      });
    return () => {
      controller.abort();
      clearTimeout(showFetchingTimeout);
    };
  }, [filters, reloadToken]);

  const loadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await fetchPageRef.current(filters, nextPage, undefined, state.kind === "ready" ? state.items : []);
      if (gen !== loadGenRef.current) return;
      setState((prev) => {
        if (prev.kind !== "ready") return prev;
        // rows added since page 1 shift offsets, so a later page can repeat one already shown
        const shown = new Set(prev.items.map(keyOf));
        const fresh = result.items.filter((item) => {
          const key = keyOf(item);
          return key === undefined || key === null || !shown.has(key);
        });
        return { kind: "ready", items: [...prev.items, ...fresh], total: result.total };
      });
      setPage(nextPage);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { state, setState, isFetching, isLoadingMore, hasMore, loadMore, reload };
}
