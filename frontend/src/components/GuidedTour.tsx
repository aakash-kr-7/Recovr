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
    target: "[data-tour='simulation-controls']",
    route: "/",
    title: "Rehearse or inspect a decision",
    body: "Live Mode plays a fixed, reproducible failure sequence for the recorded narrative. The simulator remains separate so a judge can probe individual failure scenarios without changing that story.",
  },
  {
    target: "[data-tour='recovery-funnel']",
    route: "/",
    title: "Track money through recovery",
    body: "This funnel shows what fraction of failed revenue RECOVR actually recovers, not just how many decisions it made. Confirmed recovery is kept separate from pending and expected values.",
  },
  {
    target: "[data-tour='decision-flow']",
    route: "/",
    title: "See the controls behind every action",
    body: "The flow makes the control boundary explicit: contextual reasoning can inform a decision, but economic scoring and safety checks remain authoritative before execution.",
  },
  {
    target: "[data-tour='live-decision-feed']",
    route: "/",
    title: "Follow decisions as operations happen",
    body: "The live feed connects a payment failure to its selected action, expected value and outcome. It gives an operator a traceable operational view instead of a generic AI response.",
  },
  {
    target: "[data-tour='calibration-chart']",
    route: "/results",
    title: "Audit probability quality",
    body: "Calibration compares predicted recovery probability with observed recovery on the held-out synthetic evaluation. It tests whether confidence is trustworthy, not merely whether a recommendation sounds plausible.",
  },
  {
    target: "[data-tour='audit-filters']",
    route: "/audit",
    title: "Investigate without losing traceability",
    body: "These filters narrow the audit trail by action and decision path, so an operator can inspect why a case was automated, held or routed for review while preserving the full lifecycle record.",
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
    const updateTarget = () => {
      const target = document.querySelector(step.target);
      target?.scrollIntoView({ block: "center", behavior: "auto" });
      setRect(target?.getBoundingClientRect() ?? null);
    };
    const timer = window.setTimeout(updateTarget, 100);
    window.addEventListener("resize", updateTarget);
    window.addEventListener("scroll", updateTarget, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", updateTarget);
      window.removeEventListener("scroll", updateTarget, true);
    };
  }, [open, step.target]);

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
  const tooltipStyle = spotlight
    ? {
        top: Math.min(window.innerHeight - 210, spotlight.top + spotlight.height + 14),
        left: Math.min(window.innerWidth - 370, Math.max(16, spotlight.left)),
      }
    : { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };

  return createPortal(
    <div className="guided-tour" role="dialog" aria-modal="true" aria-labelledby="guided-tour-title">
      {!spotlight && <div className="guided-tour-shade" />}
      {spotlight && <div className="guided-tour-spotlight" style={spotlight} />}
      <section className="guided-tour-card" style={tooltipStyle}>
        <p className="eyebrow">GUIDED TOUR · {stepIndex + 1} OF {steps.length}</p>
        <h2 id="guided-tour-title">{step.title}</h2>
        <p>{step.body}</p>
        <div className="guided-tour-actions">
          <button type="button" className="guided-tour-skip" onClick={onClose}>Skip tour</button>
          <div>
            <button type="button" className="guided-tour-back" onClick={() => setStepIndex((index) => Math.max(0, index - 1))} disabled={stepIndex === 0}>Back</button>
            <button type="button" className="guided-tour-next" onClick={() => stepIndex === steps.length - 1 ? onClose() : setStepIndex((index) => index + 1)}>{stepIndex === steps.length - 1 ? "Finish" : "Next"}</button>
          </div>
        </div>
      </section>
    </div>,
    document.body,
  );
}
