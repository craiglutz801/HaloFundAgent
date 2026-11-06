import { PHASES, phaseLabel } from "../api/types";

export function StageTimeline({ phase }: { phase: string }) {
  return (
    <div className="timeline" aria-label="Investment phase">
      {PHASES.map((item) => (
        <span key={item} className={item === phase ? "current" : undefined}>
          {phaseLabel(item)}
        </span>
      ))}
    </div>
  );
}
