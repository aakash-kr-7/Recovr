import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { EvaluationReport } from "@/types/api";

interface UseEvaluationReportResult {
  report: EvaluationReport | null;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches the most recent evaluation report (see backend
 * scripts/run_evaluation.py). No polling here — the report only changes
 * when the eval script is re-run, not continuously, so a one-shot fetch
 * with a manual refresh button (see ResultsPage.tsx) is the honest
 * representation of what this data actually is.
 */
export function useEvaluationReport(): UseEvaluationReportResult {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const data = await api.getLatestEvaluation();
      setReport(data);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setError(
          "No evaluation report yet. Run `python scripts/run_evaluation.py` " +
            "in the backend first.",
        );
      } else {
        setError(e instanceof ApiError ? e.message : "Failed to load report");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  return { report, loading, error };
}
