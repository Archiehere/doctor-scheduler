"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

interface State<T> {
  key: string | null;
  data?: T;
  error?: ApiError;
}

/**
 * Fetch data for a key and refetch when the key changes or `reload` is called.
 * Pass `null` as the key to skip fetching. Results for a stale key are ignored.
 */
export function useApi<T>(fetcher: () => Promise<T>, key: string | null) {
  const fetcherRef = useRef(fetcher);
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<State<T>>({ key: null });

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (key === null) return;
    let active = true;
    fetcherRef.current().then(
      (data) => active && setState({ key, data }),
      (error: unknown) =>
        active &&
        setState({
          key,
          error:
            error instanceof ApiError ? error : new ApiError(0, "unknown", "Something went wrong."),
        }),
    );
    return () => {
      active = false;
    };
  }, [key, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const setData = useCallback((data: T) => setState((s) => ({ key: s.key, data })), []);

  const current = key !== null && state.key === key;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: key !== null && !current,
    reload,
    setData,
  };
}
