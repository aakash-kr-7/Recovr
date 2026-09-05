import {
  HOW_RECOVR_WORKS_TITLE,
  HOW_RECOVR_WORKS_SUMMARY,
  HOW_RECOVR_WORKS_STEPS,
} from "@/content/explainer";

interface HowItWorksProps {
  className?: string;
  showSteps?: boolean;
}

export function HowItWorks({ className = "", showSteps = true }: HowItWorksProps) {
  return (
    <section className={`panel ${className}`.trim()}>
      <div className="panel-heading">
        <div>
          <h2>{HOW_RECOVR_WORKS_TITLE}</h2>
          <p>End-to-end payment failure triage and recovery pipeline</p>
        </div>
      </div>

      <div className="mt-3 space-y-4">
        <p className="text-100 text-slate-700 dark:text-bladeDark-textSubtle leading-relaxed">
          {HOW_RECOVR_WORKS_SUMMARY}
        </p>

        {showSteps && (
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-2">
            {HOW_RECOVR_WORKS_STEPS.map((step) => (
              <div
                key={step.step}
                className="flex flex-col p-3 rounded-card border border-slate-200 dark:border-bladeDark-borderSubtle bg-slate-50/70 dark:bg-bladeDark-surface"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand-subtle text-brand text-75 font-bold">
                    {step.step}
                  </span>
                  <span className="text-75 font-semibold text-slate-800 dark:text-bladeDark-text">
                    {step.label}
                  </span>
                </div>
                <div className="text-75 text-slate-600 dark:text-bladeDark-textSubtle leading-snug">
                  {step.description}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
