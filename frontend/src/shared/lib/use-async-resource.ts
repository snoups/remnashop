import { useCallback, useEffect, useRef, useState } from "react";

import { NetworkError } from "@shared/api/http";

export type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "error"; isNetworkError: boolean }
  | { kind: "ready"; data: T };

interface AsyncResourceOptions<T> {
  onSuccess?: (data: T) => void;
  /** refetches when these change, like an effect's dependencies */
  deps?: readonly unknown[];
  /** a deps change keeps the current data on screen instead of going back to loading */
  keepData?: boolean;
}

export function useAsyncResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  { onSuccess, deps = [], keepData = false }: AsyncResourceOptions<T> = {},
): [AsyncState<T>, () => void, (data: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<AsyncState<T>>({ kind: "loading" });
  const [reloadToken, setReloadToken] = useState(0);
  const lastReloadTokenRef = useRef(reloadToken);

  useEffect(() => {
    const controller = new AbortController();
    // reload() keeps what's on screen; a deps change starts over unless keepData
    const isReload = lastReloadTokenRef.current !== reloadToken;
    lastReloadTokenRef.current = reloadToken;
    if (!isReload && !keepData) setState((prev) => (prev.kind === "loading" ? prev : { kind: "loading" }));

    fetcher(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ kind: "ready", data });
        onSuccess?.(data);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "error", isNetworkError: err instanceof NetworkError });
      });

    return () => controller.abort();
    // fetcher/onSuccess are read per run, not tracked: callers refetch through deps or reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken, ...deps]);

  // stable identities, so a caller can list them as effect dependencies
  const reload = useCallback(() => setReloadToken((token) => token + 1), []);
  // An updater sees the latest data even when several writes land back to back;
  // it's a no-op until the first load has finished.
  const setData = useCallback(
    (data: T | ((prev: T) => T)) =>
      setState((prev) => {
        if (typeof data !== "function") return { kind: "ready", data };
        return prev.kind === "ready" ? { kind: "ready", data: (data as (prev: T) => T)(prev.data) } : prev;
      }),
    [],
  );

  return [state, reload, setData];
}
