import { useEffect, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

interface TourStep {
  target: string;
  route: string;
  title: string;
  body: string;
}

const steps: TourStep[] = [
  {
    target: "[data-tour='how-recovr-works']",
    route: "/",
    title: "Autonomous triage pipeline architecture",
    body: "RECOVR replaces brittle static retry rules with a multi-stage triage pipeline. Unambiguous declines resolve immediately via zero-latency deterministic fast paths, while complex or unmapped errors trigger LLM contextual reasoning. Crucially, all proposed actions must pass through an economic scoring gate and safety bounds before execution — ensuring every retry or dunning action generates positive expected net recovery.",
  },
  {
    target: "[data-tour='scope-and-funnel']",
    route: "/",
    title: "Measured recovery & scope honesty",
    body: "Revenue recovery numbers only matter if they reflect real money. The recovery funnel tracks confirmed net recovery against at-risk volume, separating pending reviews from actual outcomes. The 'This session' vs 'All-time' scope toggle isolates live demo runs from seeded benchmarks, giving evaluators transparent, unpadded metrics for both live testing and historical audit.",
  },
  {
    target: "[data-tour='recoveries-table']",
    route: "/recoveries",
    title: "Actionable worklist & full audit trace",
    body: "Payment operations requires total visibility rather than black-box automation. Every row in this worklist shows the exact failure diagnosis, chosen recovery action, execution status, and realized revenue. Click any row in this worklist to inspect its full decision trace: customer history, candidate scoring comparisons, and LLM rationale.",
  },
  {
    target: "[data-tour='simulation-controls']",
    route: "/",
    title: "Interactive simulation & live playback",
    body: "You can rehearse and demo RECOVR in two ways: 'Simulate payment failure' opens an interactive modal to test individual failure scenarios and edge cases on demand. 'Start Live Mode' runs a scripted 10-step sequence demonstrating edge cases, reasoning, and spend caps. Clicking 'Start Live Mode' automatically navigates to a dedicated /live command center designed for continuous live viewing.",
  },
  {
    target: "[data-tour='evaluation-comparison']",
    route: "/results",
    title: "Empirical lift & probability calibration",
    body: "Contextual recovery must prove its financial value over simpler alternatives. The baseline comparison demonstrates RECOVR's incremental net revenue lift over standard 'retry-all' and fixed-rule policies under budget caps, while the calibration reliability curve proves model confidence matches real-world recovery rates rather than hallucinated certainty.",
  },
  {
    target: "[data-tour='audit-filters']",
    route: "/audit",
    title: "Traceability & compliance filters",
    body: "Enterprise payment operations demand rigorous compliance and auditability. These filters let risk, finance, and engineering teams isolate decisions by triage path, action type, and outcome — providing a permanent, tamper-evident log proving why every single payment was automated, held, or escalated.",
  },
  {
    target: "[data-tour='about-configuration']",
    route: "/settings",
    title: "Operational bounds & safety guardrails",
    body: "RECOVR is engineered with strict production safety bounds: batch spend caps stop runaway retry costs, minimum confidence thresholds force human review on ambiguous cases, and customer attempt limits protect buyer goodwill. Sensitive API keys remain isolated in backend environments and are never exposed in client configuration.",
  },
];

interface GuidedTourProps {
  open: boolean;
  onClose: () => void;
}

export function GuidedTour({ open, onClose }: GuidedTourProps) {
  const navigate = useNavigate();
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const step = steps[stepIndex];

  useEffect(() => {
    if (!open) return;
    navigate(step.route);
  }, [navigate, open, step.route]);

  useLayoutEffect(() => {
    if (!open) return;
    let attempts = 0;
    let timer: number;
    const updateTarget = () => {
      const target = document.querySelector(step.target);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "auto" });
        setRect(target.getBoundingClientRect());
      } else if (attempts < 15) {
        attempts++;
        timer = window.setTimeout(updateTarget, 100);
      }
    };
    updateTarget();
    window.addEventListener("resize", updateTarget);
    window.addEventListener("scroll", updateTarget, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", updateTarget);
      window.removeEventListener("scroll", updateTarget, true);
    };
  }, [open, step.target, step.route]);

  useEffect(() => {
    if (!open) setStepIndex(0);
  }, [open]);

  if (!open) return null;

  const padding = 8;
  const spotlight = rect
    ? {
        top: Math.max(6, rect.top - padding),
        left: Math.max(6, rect.left - padding),
        width: Math.min(window.innerWidth - 12, rect.width + padding * 2),
        height: Math.min(window.innerHeight - 12, rect.height + padding * 2),
      }
    : null;

  let tooltipStyle: React.CSSProperties = {
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
  };

  if (spotlight) {
    const cardHeight = 270;
    const cardWidth = 370;
    const spaceBelow = window.innerHeight - (spotlight.top + spotlight.height);
    const spaceAbove = spotlight.top;

    let top: number;
    if (spaceBelow >= cardHeight + 16) {
      top = spotlight.top + spotlight.height + 14;
    } else if (spaceAbove >= cardHeight + 16) {
      top = spotlight.top - cardHeight - 14;
    } else {
      top = Math.max(16, window.innerHeight - cardHeight - 20);
    }
    const left = Math.min(window.innerWidth - cardWidth - 20, Math.max(16, spotlight.left));
    tooltipStyle = { top, left };
  }

  return createPortal(
    <div
      className="guided-tour"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guided-tour-title"
    >
      {!spotlight && <div className="guided-tour-shade" />}
      {spotlight && <div className="guided-tour-spotlight" style={spotlight} />}
      <section className="guided-tour-card" style={tooltipStyle}>
        <p className="eyebrow">
          GUIDED TOUR · {stepIndex + 1} OF {steps.length}
        </p>
        <h2 id="guided-tour-title">{step.title}</h2>
        <p>{step.body}</p>
        <div className="guided-tour-actions">
          <button type="button" className="guided-tour-skip" onClick={onClose}>
            Skip tour
          </button>
          <div>
            <button
              type="button"
              className="guided-tour-back"
              onClick={() => setStepIndex((index) => Math.max(0, index - 1))}
              disabled={stepIndex === 0}
            >
              Back
            </button>
            <button
              type="button"
              className="guided-tour-next"
              onClick={() =>
                stepIndex === steps.length - 1
                  ? onClose()
                  : setStepIndex((index) => index + 1)
              }
            >
              {stepIndex === steps.length - 1 ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </section>
    </div>,
    document.body,
  );
}
