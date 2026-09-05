"""
The confidence gate: decides whether a failed transaction's decline
reason is unambiguous enough for the deterministic fast path, or needs
the Claude reasoning path.

See docs/decisions/0003-two-path-agent.md for why this split exists.
"""

from app.agent.rules.decline_taxonomy import FAST_PATH_TABLE
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction, TriagePath


class GateDecision:
    def __init__(self, path: TriagePath, fast_path_action: TriageAction | None = None,
                 fast_path_reasoning: str | None = None):
        self.path = path
        self.fast_path_action = fast_path_action
        self.fast_path_reasoning = fast_path_reasoning


def route(transaction: Transaction) -> GateDecision:
    """Look up the transaction's normalized decline_reason. If it's in
    the fast-path table, return the fixed action immediately with no
    model call. Otherwise route to the reasoning path.

    Unrecognized decline reasons (not in FAST_PATH_TABLE and not in
    ROUTED_TO_REASONING_PATH either — i.e. genuinely novel strings) also
    fall through to the reasoning path. This is deliberate: an unknown
    code is, by definition, not something we've asserted is unambiguous.
    See docs/POSITIONING.md, claim #2, for why this matters as a
    differentiator from a pure rules engine.
    """
    entry = FAST_PATH_TABLE.get(transaction.decline_reason)
    if entry is not None:
        action, reasoning = entry
        return GateDecision(
            path=TriagePath.DETERMINISTIC,
            fast_path_action=action,
            fast_path_reasoning=reasoning,
        )
    return GateDecision(path=TriagePath.REASONING)
