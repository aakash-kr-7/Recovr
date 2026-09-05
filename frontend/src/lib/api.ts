const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.text();
    let errorMessage = body;
    try {
      const json = JSON.parse(body);
      if (json.detail) errorMessage = json.detail;
    } catch {
      // Ignored
    }
    throw new ApiError(errorMessage || `Error ${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getRecentTransactions: (limit = 50, scope = "session") =>
    request<import("@/types/api").RecentTransaction[]>(
      `/transactions/recent?limit=${limit}&scope=${scope}`,
    ),
  getRecoveryFunnel: (scope = "session") =>
    request<import("@/types/api").RecoveryFunnelSummary>(
      `/transactions/funnel-summary?scope=${scope}`,
    ),
  getAuditDetail: (transactionId: string) =>
    request<import("@/types/api").AuditDetail>(
      `/transactions/audit/${transactionId}`,
    ),
  getLatestEvaluation: () =>
    request<import("@/types/api").EvaluationReport>("/evaluation/latest"),
  getDemoPresets: () =>
    request<
      {
        name: string;
        payload: {
          amount_inr: number;
          decline_reason: string;
          customer_history: Record<string, unknown>;
        };
      }[]
    >("/demo/presets"),
  simulateDemo: (payload: Record<string, unknown>) =>
    request<{
      status: string;
      transaction_id: string;
      execution_status: string;
      provider_reference: string | null;
      is_demo_simulated: boolean;
    }>("/demo/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getLiveModeStatus: () =>
    request<import("@/types/api").LiveModeStatus>("/demo/live-mode/status"),
  startLiveMode: () =>
    request<{ status: string; sequence_length?: number }>("/demo/live-mode/start", {
      method: "POST",
    }),
  stopLiveMode: () =>
    request<{ status: string }>("/demo/live-mode/stop", { method: "POST" }),
  getPublicConfig: () =>
    request<import("@/types/api").PublicConfig>("/config/public"),
};
