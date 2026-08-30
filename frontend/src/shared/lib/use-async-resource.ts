import { useEffect, useState } from "react";

import { NetworkError } from "@shared/api/http";

export type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "error"; isNetworkError: boolean }
  | { kind: "ready"; data: T };

export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  onSuccess?: (data: T) => void,
): [AsyncState<T>, () => void, (data: T) => void] {
  const [state, setState] = useState<AsyncState<T>>({ kind: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    fetcher()
      .then((data) => {
        if (cancelled) return;
        setState({ kind: "ready", data });
        onSuccess?.(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ kind: "error", isNetworkError: err instanceof NetworkError });
      });

    return () => {
      cancelled = true;
    };
    // fetcher/onSuccess are read once per effect run (mount, or an explicit
    // reload()) rather than tracked as dependencies -- every call site fetches
    // once and only refetches on demand via the returned reload(), matching
    // the hand-written effects this hook replaces.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  const reload = () => setReloadToken((token) => token + 1);
  const setData = (data: T) => setState({ kind: "ready", data });

  return [state, reload, setData];
}
