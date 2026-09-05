import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money } from "@/lib/operations";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";

import { type RecentTransaction } from "@/types/api";

export function ActivityTable({
  transactions,
  onHoverTransaction,
}: {
  transactions: ReturnType<typeof useRecentTransactions>["transactions"];
  onHoverTransaction?: (tx: RecentTransaction | null) => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const highlightId = location.state?.highlightId;
  const [flashing, setFlashing] = useState<string | null>(highlightId || null);

  useEffect(() => {
    if (highlightId) {
      setFlashing(highlightId);
      const timer = setTimeout(() => setFlashing(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [highlightId]);

  return (
    <div className="table-scroll">
      <table className="operations-table">
        <thead>
          <tr>
            <th>Payment</th>
            <th>Amount</th>
            <th>Failure</th>
            <th>Action</th>
            <th>Status</th>
            <th>Expected net</th>
            <th>Outcome</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((item) => (
            <tr
              key={item.transaction_id}
              className={`clickable-row ${
                flashing === item.transaction_id
                  ? "bg-brand-subtle transition-colors duration-1000"
                  : "transition-colors duration-1000"
              }`}
              onClick={(e) => {
                if ((e.target as HTMLElement).closest("a, button")) return;
                navigate(`/decisions/${item.transaction_id}`);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/decisions/${item.transaction_id}`);
                }
              }}
              title="Click to view decision detail"
              onMouseEnter={() => onHoverTransaction?.(item as RecentTransaction)}
              onMouseLeave={() => onHoverTransaction?.(null)}
            >
              <td>
                <Link
                  className="table-link"
                  to={`/decisions/${item.transaction_id}`}
                  onClick={(e) => e.stopPropagation()}
                >
                  {item.transaction_id.slice(0, 12)}…
                </Link>
                {item.is_synthetic && (
                  <span className="demo-label">DEMO DATA</span>
                )}
              </td>
              <td>{money(item.amount_inr)}</td>
              <td>{item.decline_reason}</td>
              <td>{ACTION_LABELS[item.action]}</td>
              <td>
                <StatusBadge
                  outcome={item.recovery_outcome}
                  synthetic={item.is_synthetic}
                />
              </td>
              <td>{money(item.selected_expected_net_recovery_inr)}</td>
              <td>
                <OutcomeBadge outcome={item.recovery_outcome} />
              </td>
              <td>{new Date(item.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
