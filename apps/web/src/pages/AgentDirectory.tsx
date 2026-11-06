import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAgents } from "../api/generated";
import { filterQuery } from "../api/queries";

type Project = {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  status: string;
};

type Directory = {
  agents: {
    id: string;
    name: string;
    job: string;
    output: string;
    owner: string;
    company_count: number;
    project_count: number;
    projects?: Project[];
  }[];
  applied_filters?: Record<string, unknown>;
};

export function AgentDirectory({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const search = params.toString();
  const query = useQuery({
    queryKey: ["agents", principalId, search],
    queryFn: () => getAgents(filterQuery(search)) as Promise<Directory>,
  });
  if (query.isLoading) return <div className="skeleton" />;
  const selected = params.get("agent");
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Agents</h1>
          <p>Counts are companies and projects. Several runs on one project still count as one project.</p>
        </div>
      </header>
      <div className="grid three">
        {query.data?.agents.map((agent) => (
          <Link
            className="card company-card"
            key={agent.id}
            to={search ? `/agents/${agent.id}?${search}` : `/agents/${agent.id}`}
            aria-current={selected === agent.id ? "page" : undefined}
          >
            <p className="kicker">{agent.output}</p>
            <h2>{agent.name}</h2>
            <p>{agent.job}</p>
            <p className="meta">
              {agent.owner} · {agent.company_count} companies · {agent.project_count} projects
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
