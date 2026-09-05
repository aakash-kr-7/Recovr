import { ActivityTable } from "@/pages/DashboardPage";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";

export function TransactionsPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  return <div className="page-stack"><section className="page-heading"><div><p className="eyebrow">PAYMENT FAILURE LEDGER</p><h1>Transactions</h1><p>All failed-payment records currently available through the operations API.</p></div></section>{loading && !transactions.length ? <div className="state">Loading transactions…</div> : error ? <div className="state state-error">{error}</div> : !transactions.length ? <div className="state">No failed payments are available.</div> : <section className="panel"><ActivityTable transactions={transactions} /></section>}</div>;
}
