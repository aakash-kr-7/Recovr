import { ActivityTable } from "@/components/ActivityTable";
import { PageHeader } from "@/components/PageHeader";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { PageContext } from "@/components/PageContext";

export function TransactionsPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="ALL HISTORICAL TRANSACTIONS · RAW LEDGER"
        title="Transactions"
        description="Complete immutable ledger of all failed payments across every lifecycle status (open, held, resolved, escalated) — distinct from the active Recoveries worklist."
      >
        {transactions.length > 0 && (
          <span className="badge badge-neutral">
            {transactions.length} total records
          </span>
        )}
      </PageHeader>
      {loading && !transactions.length ? (
        <div className="state">Loading transactions…</div>
      ) : error ? (
        <div className="state state-error">{error}</div>
      ) : !transactions.length ? (
        <div className="state">No failed payments are available.</div>
      ) : (
        <section className="panel">
          <ActivityTable transactions={transactions} />
        </section>
      )}

      <PageContext>
        This is the full historical record of all processed items, regardless of outcome. Use this to see absolutely everything that flowed through the system, not just what currently needs attention.
      </PageContext>
    </div>
  );
}
