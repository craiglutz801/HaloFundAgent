import { Link } from "react-router-dom";
import { RunStatus } from "./RunStatus";

export function WorkstreamTrack({
  companyId,
  agent,
  phase,
  status,
  detail,
}: {
  companyId: string;
  agent: string;
  phase: string;
  status: string;
  detail: string;
}) {
  return (
    <article className="card track">
      <strong>{agent}</strong>
      <div>
        <div>
          {phase} · <RunStatus status={status} />
        </div>
        <div className="muted">{detail || "No status detail"}</div>
      </div>
      <Link to={`/companies/${companyId}/agents/${agent}`}>Open</Link>
    </article>
  );
}
