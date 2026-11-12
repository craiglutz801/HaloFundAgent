import { PHASES, PHASE_SHORT, phaseLabel } from "../api/types";

export function StageTimeline({ phase }: { phase: string }) {
  const current = PHASES.indexOf(phase as (typeof PHASES)[number]);
  return (
    <div className="timeline" aria-label="Investment phase">
      {PHASES.map((item, index) => (
        <span key={item} className={item === phase ? "current" : current > index ? "done" : undefined} title={phaseLabel(item)}>
          {PHASE_SHORT[item] ?? phaseLabel(item)}
        </span>
      ))}
    </div>
  );
}
