"use client";

import { useCallback, useEffect, useState } from "react";
import type { SectionStatus } from "@/components/dashboard/section";

/** Per-request fetch state with isolated loading/error and manual retry. */
export function useSection<T>(
  fetcher: () => Promise<T | null>,
  enabled: boolean,
  reloadKey: unknown = null
): {
  status: SectionStatus;
  data: T | null;
  retry: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<SectionStatus>({ state: "loading" });
  const [nonce, setNonce] = useState(0);

  const retry = useCallback(() => {
    setStatus({ state: "loading" });
    setNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    fetcher().then((result) => {
      if (!active) return;
      if (result === null) {
        setStatus({
          state: "error",
          message: "The service did not return data.",
        });
      } else {
        setData(result);
        setStatus({ state: "ready" });
      }
    });
    return () => {
      active = false;
    };
  }, [enabled, nonce, reloadKey, fetcher]);

  return { status, data, retry };
}
