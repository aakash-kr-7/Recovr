import type { RecoveryOutcome } from "@/types/api";
import { executionBadge, outcomeBadge } from "@/lib/operations";

export function StatusBadge({ outcome, synthetic }: { outcome: RecoveryOutcome | null; synthetic: boolean }) { const badge = executionBadge(outcome, synthetic); return <span className={`badge ${badge.className}`}>{badge.label}</span>; }
export function OutcomeBadge({ outcome }: { outcome: RecoveryOutcome | null }) { const badge = outcomeBadge(outcome); return <span className={`badge ${badge.className}`}>{badge.label}</span>; }
