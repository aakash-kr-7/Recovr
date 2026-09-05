"""
The fast-path decision table: decline codes unambiguous enough that no
transaction context changes the correct action.

Every entry here is a deliberate claim: "no plausible context makes a
different action correct for this code." That claim should be defensible
out loud, not just convenient. When in doubt, leave a code out of this
table — it will fall through to the reasoning path by default (see
app/agent/gate.py), which is the safer failure mode.

Decline reason strings below are a best-effort starting point based on
common UPI/card failure categories. CONFIRM against Razorpay's actual
test-mode error codes during Day 1 setup — see the note in
backend/README.md — and update this table to match reality rather than
this guess.
"""

from app.schemas.triage import TriageAction

# decline_reason (normalized) -> (action, human-readable reasoning template)
FAST_PATH_TABLE: dict[str, tuple[TriageAction, str]] = {
    "card_reported_lost_or_stolen": (
        TriageAction.ESCALATE_TO_DUNNING,
        "Card reported lost or stolen. No retry is ever appropriate "
        "regardless of context — escalating directly.",
    ),
    "account_closed": (
        TriageAction.NO_ACTION,
        "Account closed. Retrying serves no purpose and risks additional "
        "fees. No action taken.",
    ),
    "card_expired": (
        TriageAction.ESCALATE_TO_DUNNING,
        "Card expired. Customer needs to update their payment method — "
        "this is not something a retry or rail switch can fix.",
    ),
    "invalid_card_number": (
        TriageAction.NO_ACTION,
        "Invalid card number. Likely a data-entry or integration error, "
        "not a transient failure. No automatic action taken.",
    ),
    "compliance_block": (
        TriageAction.HOLD_FOR_REVIEW,
        "Compliance or risk block. This requires human review by policy, "
        "never an automatic retry.",
    ),
}

# Codes deliberately NOT in the table above, with the reason they're
# routed to the reasoning path instead. Documented here so the boundary
# is a visible decision, not an accidental omission.
ROUTED_TO_REASONING_PATH = {
    "insufficient_funds": (
        "Whether this is worth retrying depends heavily on the "
        "customer's history — a repeat pattern signals real financial "
        "distress; an isolated instance for an otherwise clean customer "
        "is often a timing issue."
    ),
    "bank_timeout": (
        "Almost always transient, but the right rail and timing for the "
        "retry benefits from knowing the customer's usual successful "
        "payment method."
    ),
    "authentication_failed": (
        "Could be a genuine 3DS/AFA friction issue (retry with explicit "
        "re-auth prompt) or a signal of a compromised card being tested "
        "(do not retry). Context distinguishes these."
    ),
    "issuer_unavailable": (
        "Often correlates with known bank-side outages — worth checking "
        "whether this decline lines up with a broader pattern before "
        "deciding on immediate retry vs. delayed batch retry."
    ),
}
