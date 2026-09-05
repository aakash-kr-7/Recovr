import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { RecoveryFunnelSummary } from "@/types/api";
import { RECENT_TRANSACTIONS_POLL_INTERVAL_MS } from "@/hooks/useRecentTransactions";

export function useRecoveryFunnel() {
  const [summary, setSummary] = useState<RecoveryFunnelSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchSummary() {
      try {
        const next = await api.getRecoveryFunnel();
        if (!cancelled) {
          setSummary(next);
          setError(null);
        }
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof ApiError ? reason.message : "Failed to load recovery funnel");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchSummary();
    const poll = window.setInterval(fetchSummary, RECENT_TRANSACTIONS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(poll);
    };
  }, []);

  return { summary, loading, error };
}
