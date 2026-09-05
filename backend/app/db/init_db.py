"""Creates all tables. Called once at app startup (see app/main.py).

Deliberately no migration framework (e.g. Alembic) for this build — the
schema is small and stable enough that a one-week solo project doesn't
benefit from migration tooling overhead. If this project grows past the
buildathon, that's the first piece of infra to add back.
"""

from sqlalchemy import inspect, text

from app.db.session import Base, engine

# Import models so they're registered on Base.metadata before create_all.
from app.models import audit_entry, transaction  # noqa: F401
from app.models import recovery_decision, recovery_outcome  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # SQLite create_all does not evolve existing demo databases. These are
    # additive columns only; unique indexes provide durable webhook/outcome
    # idempotency on existing installations too.
    additions = {
        "recovery_outcomes": {
            "provider": "VARCHAR", "provider_reference": "VARCHAR", "mode": "VARCHAR DEFAULT 'BOUNDED_SIMULATION'",
            "amount_attempted": "FLOAT DEFAULT 0", "action_cost_inr": "FLOAT DEFAULT 0", "risk_penalty_inr": "FLOAT DEFAULT 0",
            "net_recovered_inr": "FLOAT", "error_code": "VARCHAR", "error_message": "VARCHAR",
            "outcome_source": "VARCHAR DEFAULT 'executor'",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_payment_id ON transactions(razorpay_payment_id)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_outcomes_transaction ON recovery_outcomes(transaction_id)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_outcomes_provider_reference ON recovery_outcomes(provider_reference)"))
