import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { HowItWorks } from "@/components/HowItWorks";
import { api } from "@/lib/api";
import { money, percent } from "@/lib/operations";
import type { PublicConfig } from "@/types/api";

export function SettingsPage() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getPublicConfig()
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Unable to load system settings",
        );
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="SYSTEM ARCHITECTURE & CONFIGURATION"
          title="About & Configuration"
          description="Read-only operational configuration and safety bounds for evaluation."
        />
        <div className="state">Loading operational configuration…</div>
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="SYSTEM ARCHITECTURE & CONFIGURATION"
          title="About & Configuration"
          description="Read-only operational configuration and safety bounds for evaluation."
        />
        <div className="state state-error">
          {error ?? "System settings unavailable"}
        </div>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM ARCHITECTURE & CONFIGURATION"
        title="About & Configuration"
        description="System pipeline overview, operational parameters, and safety bounds exposed via GET /config/public. Secrets and private credentials are never exposed."
      />

      {/* a. How RECOVR works - short, plain-English explainer of the actual pipeline */}
      <HowItWorks />

      {/* Operational configuration & Provider safety */}
      <div className="content-grid">
        {/* b. Operational configuration - existing real, non-misleading fields only */}
        <section className="panel" data-tour="about-configuration">
          <div className="panel-heading">
            <div>
              <h2>Operational configuration</h2>
              <p>Active runtime parameters and bounded executor thresholds</p>
            </div>
          </div>
          <dl className="definition-list">
            <div>
              <dt>LLM Provider</dt>
              <dd>
                <code className="font-mono text-75 font-semibold text-slate-800 dark:text-bladeDark-text bg-slate-100 dark:bg-bladeDark-surface px-1.5 py-0.5 rounded-2xsmall">
                  {config.llm_provider}
                </code>
              </dd>
            </div>
            {config.active_model && (
              <div>
                <dt>Active model</dt>
                <dd>
                  <code className="font-mono text-75 text-slate-700 dark:text-bladeDark-textSubtle">
                    {config.active_model}
                  </code>
                </dd>
              </div>
            )}
            <div>
              <dt>Batch spend cap</dt>
              <dd>{money(config.batch_spend_cap_inr)}</dd>
            </div>
            <div>
              <dt>Min auto confidence</dt>
              <dd>{percent(config.min_auto_execute_confidence)}</dd>
            </div>
            <div>
              <dt>Max customer attempts</dt>
              <dd>{config.max_customer_recovery_attempts} attempts</dd>
            </div>
            <div>
              <dt>App environment</dt>
              <dd>{config.environment}</dd>
            </div>
          </dl>
        </section>

        {/* c. Provider & credential safety - section stays as-is */}
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Provider & credential safety</h2>
              <p>Security guarantees, sandboxing, and isolation</p>
            </div>
          </div>
          <dl className="definition-list">
            <div>
              <dt>Execution mode</dt>
              <dd>
                {config.has_real_razorpay_credentials ? (
                  <span className="badge badge-provider">
                    REAL RAZORPAY TEST-MODE
                  </span>
                ) : (
                  <span className="badge badge-sim">
                    DEMO / SEEDED DATA ONLY
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Credential status</dt>
              <dd>{config.data_mode_label}</dd>
            </div>
            <div>
              <dt>Money movement</dt>
              <dd>
                Disabled. The system operates strictly within safe test/sandbox
                bounds. No real funds are at risk.
              </dd>
            </div>
            <div>
              <dt>Public contract</dt>
              <dd>
                Exposed via{" "}
                <code className="font-mono text-75 text-slate-700 dark:text-bladeDark-textSubtle">
                  GET /config/public
                </code>
                .
              </dd>
            </div>
            <div>
              <dt>Secret isolation</dt>
              <dd>
                API keys, webhook secrets, and database credentials are
                explicitly excluded from client contracts.
              </dd>
            </div>
          </dl>
        </section>
      </div>

      {/* d. Economic cost baseline (ADR 0004) - framed as "why these numbers" */}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Economic cost baseline (ADR 0004)</h2>
            <p>
              Why these numbers: each recovery action is scored by expected net
              rupee value (expected recovery minus execution cost). These
              baseline constants calibrate the optimizer so it never recommends
              a recovery action that costs more than it recovers.
            </p>
          </div>
        </div>
        <dl className="definition-list">
          <div>
            <dt>Wasted retry cost</dt>
            <dd>{money(config.wasted_retry_cost_inr)}</dd>
          </div>
          <div>
            <dt>Alternate rail cost</dt>
            <dd>{money(config.alternate_rail_cost_inr)}</dd>
          </div>
          <div>
            <dt>Review cost</dt>
            <dd>{money(config.review_cost_inr)}</dd>
          </div>
          <div>
            <dt>Dunning cost</dt>
            <dd>{money(config.dunning_cost_inr)}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
