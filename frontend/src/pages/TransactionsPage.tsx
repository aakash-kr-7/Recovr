import { ActivityTable } from "@/components/ActivityTable";
import { PageHeader } from "@/components/PageHeader";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";

export function TransactionsPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="PAYMENT FAILURE LEDGER"
        title="Transactions"
        description="All failed-payment records currently available through the operations API."
      />
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
    </div>
  );
}
