import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { RecentTransaction } from "@/types/api";

export const RECENT_TRANSACTIONS_POLL_INTERVAL_MS = 4000;

interface UseRecentTransactionsResult {
  transactions: RecentTransaction[];
  loading: boolean;
  error: string | null;
}

/**
 * Polls GET /transactions/recent on an interval so the dashboard's live
 * decision feed updates as new webhook events or evaluation runs write
 * new audit entries. Simple polling rather than websockets — deliberate
 * for a one-week solo build; see docs/decisions/ if this needs revisiting.
 */
export function useRecentTransactions(limit = 50): UseRecentTransactionsResult {
  const [transactions, setTransactions] = useState<RecentTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchOnce() {
      try {
        const data = await api.getRecentTransactions(limit);
        if (!cancelled) {
          setTransactions(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError ? e.message : "Failed to load transactions",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchOnce();
    const interval = setInterval(fetchOnce, RECENT_TRANSACTIONS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [limit]);

  return { transactions, loading, error };
}
