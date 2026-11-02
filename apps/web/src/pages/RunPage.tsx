import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { RunStatus } from "../components/RunStatus";

type RunDetail = {
  id: string;
  agent_name: string;
  phase: string;
  status: string;
  status_detail: string;
  company_id: string | null;
  company_name: string | null;
  comparison_locked: boolean;
  artifacts: { id: string; kind: string; sha256: string; content: { summary?: string } }[];
};

export function RunPage({ principalId }: { principalId: string }) {
  const { runId = "", companyId = "" } = useParams();
  const query = useQuery({
    queryKey: ["run", principalId, runId],
    queryFn: () => api<RunDetail>(`/api/v1/runs/${runId}`),
  });
  if (query.isLoading) return <div className="skeleton" />;
  if (!query.data) return <p className="empty">Run not found.</p>;
  const run = query.data;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">{run.company_name}</p>
          <h1>
            {run.agent_name} · {run.phase}
          </h1>
          <RunStatus status={run.status} />
          <p>{run.status_detail}</p>
        </div>
      </header>
      {run.comparison_locked && <p className="badge independence">Comparison access is locked.</p>}
      {run.artifacts.map((artifact) => (
        <article className="card" key={artifact.id}>
          <h2>{artifact.kind}</h2>
          <p>{artifact.content.summary}</p>
          <p className="hash">{artifact.sha256}</p>
        </article>
      ))}
      <Link to={`/companies/${companyId}`}>Back to company</Link>
    </>
  );
}
