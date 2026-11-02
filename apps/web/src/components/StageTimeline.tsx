import { STAGES, stageLabel } from "../api/types";

export function StageTimeline({ stage }: { stage: string }) {
  return (
    <div className="timeline" aria-label="Company stage">
      {STAGES.map((item) => (
        <span key={item} className={item === stage ? "current" : undefined}>
          {stageLabel(item)}
        </span>
      ))}
    </div>
  );
}
