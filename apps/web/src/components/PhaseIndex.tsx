import { Link, useSearchParams } from "react-router-dom";
import { PHASES, PHASE_SHORT, phaseLabel } from "../api/types";

export function PhaseIndex({ counts }: { counts: { stage: string; count: number }[] }) {
  const [params] = useSearchParams();
  const current = params.get("phase") ?? "";
  const byPhase = new Map(counts.map((item) => [item.stage, item.count]));
  return (
    <nav className="phase-index" aria-label="Phases">
      {PHASES.map((phase) => {
        const count = byPhase.get(phase) ?? 0;
        const hidden = count < 0;
        const next = new URLSearchParams(params);
        if (current === phase) next.delete("phase");
        else next.set("phase", phase);
        next.delete("outcome");
        const search = next.toString();
        return (
          <Link
            key={phase}
            className={count === 0 || hidden ? "is-empty" : undefined}
            to={search ? `/companies?${search}` : "/companies"}
            aria-current={current === phase ? "true" : undefined}
            title={phaseLabel(phase)}
          >
            <span className="count">{hidden ? "—" : count}</span>
            <span className="label">{PHASE_SHORT[phase] ?? phaseLabel(phase)}</span>
          </Link>
        );
      })}
    </nav>
  );
}
