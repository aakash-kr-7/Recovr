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

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(`${res.status} on ${path}: ${body}`, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getRecentTransactions: (limit = 50) =>
    request<import("@/types/api").RecentTransaction[]>(
      `/transactions/recent?limit=${limit}`,
    ),
  getAuditDetail: (transactionId: string) =>
    request<import("@/types/api").AuditDetail>(
      `/transactions/audit/${transactionId}`,
    ),
  getLatestEvaluation: () =>
    request<import("@/types/api").EvaluationReport>("/evaluation/latest"),
};
