"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { CaseDetail } from "@/lib/types";

export function useCaseDetail(caseId: string): {
  caseDetail: CaseDetail | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
} {
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const refetch = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<CaseDetail>(`/api/cases/${caseId}`)
      .then((body) => {
        if (!cancelled) setCaseDetail(body);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, nonce]);

  return { caseDetail, loading, error, refetch };
}
