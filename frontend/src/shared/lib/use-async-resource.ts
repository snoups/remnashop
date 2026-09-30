import { useEffect, useState } from "react";

import { NetworkError } from "@shared/api/http";

export type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "error"; isNetworkError: boolean }
  | { kind: "ready"; data: T };

export function useAsyncResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  onSuccess?: (data: T) => void,
): [AsyncState<T>, () => void, (data: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<AsyncState<T>>({ kind: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

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
    // fetcher/onSuccess are read once per effect run (mount, or an explicit
    // reload()) rather than tracked as dependencies -- every call site fetches
    // once and only refetches on demand via the returned reload(), matching
    // the hand-written effects this hook replaces.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  const reload = () => setReloadToken((token) => token + 1);
  // An updater sees the latest data even when several writes land back to back;
  // it's a no-op until the first load has finished.
  const setData = (data: T | ((prev: T) => T)) =>
    setState((prev) => {
      if (typeof data !== "function") return { kind: "ready", data };
      return prev.kind === "ready" ? { kind: "ready", data: (data as (prev: T) => T)(prev.data) } : prev;
    });

  return [state, reload, setData];
}
