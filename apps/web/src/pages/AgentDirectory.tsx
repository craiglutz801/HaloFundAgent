import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAgents } from "../api/generated";
import { filterQuery } from "../api/queries";
import { FilterBar } from "../components/FilterBar";

type Project = {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  status: string;
  insight?: string;
  objective?: string;
};

type AgentCard = {
  id: string;
  name: string;
  job: string;
  output: string;
  owner: string;
  company_count: number;
  project_count: number;
  projects?: Project[];
};

type Directory = {
  agents: AgentCard[];
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
  const narrowed = ["q", "agent", "phase", "company", "outcome"].some((key) => params.get(key));
  const agents = query.data?.agents ?? [];
  const working = agents.filter((agent) => companyNames(agent.projects).length > 0);
  const standby = narrowed ? [] : agents.filter((agent) => companyNames(agent.projects).length === 0);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">Desk</p>
          <h1>Agents</h1>
          <p>Who is on a company right now. Past work stays in the project scope.</p>
        </div>
      </header>
      <FilterBar />
      {working.length === 0 && <p className="empty">No specialist has a company in this view.</p>}
      <div className="agent-list">
        {working.map((agent) => (
          <AgentTile key={agent.id} agent={agent} search={search} selected={selected} />
        ))}
      </div>
      {standby.length > 0 && (
        <section className="standby-block">
          <h2>Standing by</h2>
          <div className="standby">
            {standby.map((agent) => (
              <Link key={agent.id} to={search ? `/agents/${agent.id}?${search}` : `/agents/${agent.id}`}>
                {agent.name}
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function AgentTile({ agent, search, selected }: { agent: AgentCard; search: string; selected: string | null }) {
  const projects = agent.projects ?? [];
  return (
    <Link
      className="card agent-tile"
      to={search ? `/agents/${agent.id}?${search}` : `/agents/${agent.id}`}
      aria-current={selected === agent.id ? "page" : undefined}
    >
      <div>
        <p className="kicker">{agent.output.replace(/([a-z])([A-Z])/g, "$1 $2")}</p>
        <h2>{agent.name}</h2>
        <p>{agent.job}</p>
      </div>
      <ul className="agent-book">
        {projects.map((project) => (
          <li key={project.id}>
            <span>{project.company_name}</span>
            <span>{project.insight || project.objective || project.title}</span>
          </li>
        ))}
      </ul>
    </Link>
  );
}
