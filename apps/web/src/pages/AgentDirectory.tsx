import { useEffect } from "react";
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

function companyNames(projects: Project[] | undefined) {
  const names: string[] = [];
  for (const project of projects ?? []) {
    if (project.company_name && !names.includes(project.company_name)) names.push(project.company_name);
  }
  return names;
}

export function AgentDirectory({ principalId }: { principalId: string }) {
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    if (!params.get("scope")) {
      const next = new URLSearchParams(params);
      next.set("scope", "active");
      setParams(next, { replace: true });
    }
  }, [params, setParams]);
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
          <p>Each specialist, and the companies they are working now.</p>
        </div>
      </header>
      <div className="agent-list">
        {query.data?.agents.map((agent) => {
          const companies = companyNames(agent.projects);
          return (
            <Link
              className="card agent-tile"
              key={agent.id}
              to={search ? `/agents/${agent.id}?${search}` : `/agents/${agent.id}`}
              aria-current={selected === agent.id ? "page" : undefined}
            >
              <p className="kicker">{agent.output}</p>
              <h2>{agent.name}</h2>
              <p>{agent.job}</p>
              <p className="agent-companies">
                {companies.length > 0 ? companies.join(" · ") : "No companies in this view"}
              </p>
            </Link>
          );
        })}
      </div>
    </>
  );
}
