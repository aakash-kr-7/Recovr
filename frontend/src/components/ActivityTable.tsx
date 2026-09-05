import { Link } from "react-router-dom";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money } from "@/lib/operations";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";

export function ActivityTable({
  transactions,
}: {
  transactions: ReturnType<typeof useRecentTransactions>["transactions"];
}) {
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
            <tr key={item.transaction_id}>
              <td>
                <Link
                  className="table-link"
                  to={`/decisions/${item.transaction_id}`}
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
