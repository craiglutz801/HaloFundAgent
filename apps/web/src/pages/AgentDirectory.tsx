import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

type Directory = {
  agents: { id: string; name: string; job: string; output: string; owner: string; visible_runs: number }[];
};

export function AgentDirectory({ principalId }: { principalId: string }) {
  const query = useQuery({
    queryKey: ["agents", principalId],
    queryFn: () => api<Directory>("/api/v1/agents"),
  });
  if (query.isLoading) return <div className="skeleton" />;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Agents</h1>
          <p>Nine specialists. Counts include only runs in workspaces you can read.</p>
        </div>
      </header>
      <div className="grid three">
        {query.data?.agents.map((agent) => (
          <Link className="card company-card" key={agent.id} to={`/agents/${agent.id}`}>
            <p className="kicker">{agent.output}</p>
            <h2>{agent.name}</h2>
            <p>{agent.job}</p>
            <p className="meta">
              {agent.owner} · {agent.visible_runs} visible runs
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
