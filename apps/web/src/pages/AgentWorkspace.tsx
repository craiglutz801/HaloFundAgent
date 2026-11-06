import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAgents } from "../api/generated";
import { filterQuery, useCompany } from "../api/queries";
import { RunStatus } from "../components/RunStatus";

const COPY: Record<string, { name: string; job: string }> = {
  gm: { name: "GM", job: "Coordination stays with people. A prompt cannot skip a gate." },
  scout: { name: "Scout", job: "Missing dimensions stay empty. Fit is not a probability." },
  ainge: { name: "Ainge", job: "Numeric conclusions cite inputs. Gross MOIC is not a net fund return." },
  xavier: { name: "Xavier", job: "Four lenses. An evidence gap stays unscored. There is no overall score." },
  mutombo: { name: "Mutombo", job: "The independent pass is sealed before comparison grants open." },
  stockton: { name: "Stockton", job: "Tagged activity is not revenue. Inventory is not booked from a thesis." },
  sloan: { name: "Sloan", job: "Estimated capacity is not cash saved." },
  trainer: { name: "Trainer", job: "Missing or stale required reporting is unknown, not green." },
  scorekeeper: { name: "Scorekeeper", job: "Decisions stay tied to the packet hash that was approved." },
};

export function AgentWorkspace({ principalId }: { principalId: string }) {
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const agentId = params.agentId ?? "";
  const companyId = params.companyId;
  useEffect(() => {
    if (!searchParams.get("scope")) {
      const next = new URLSearchParams(searchParams);
      next.set("scope", "active");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  const company = useCompany(principalId, companyId, searchParams.toString());
  const directory = useQuery({
    queryKey: ["agent-projects", principalId, agentId, searchParams.toString()],
    queryFn: () =>
      getAgents(filterQuery(searchParams.toString())) as Promise<{
        agents: {
          id: string;
          projects: { id: string; company_id: string; company_name: string; title: string; status: string; objective: string }[];
        }[];
      }>,
    enabled: !companyId,
  });
  const profile = COPY[agentId] ?? { name: agentId, job: "" };
  const runs = (company.data?.runs ?? []).filter((run) => run.agent_name === agentId);
  const projects = directory.data?.agents.find((agent) => agent.id === agentId)?.projects ?? [];
  const visibleProjects = companyId
    ? (company.data?.assignments ?? []).filter((item) => item.agent_id === agentId)
    : projects;
  const artifacts = company.data?.artifacts.filter((artifact) => runs.some((run) => run.id === artifact.run_id)) ?? [];
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">{company.data?.company.display_name ?? "Specialist"}</p>
          <h1>{profile.name}</h1>
          <p>{profile.job}</p>
        </div>
      </header>
      {!companyId && projects.length === 0 && !directory.isLoading && (
        <p className="empty">No projects match this filter.</p>
      )}
      {visibleProjects.map((project) => (
        <article className="card" key={project.id}>
          <p className="kicker">{"company_name" in project ? project.company_name : company.data?.company.display_name}</p>
          <h2>{project.title}</h2>
          <p>{"objective" in project ? project.objective : ""}</p>
          <p className="meta">{project.status.replaceAll("_", " ")}</p>
          <Link
            to={`/companies/${"company_id" in project ? project.company_id : companyId}/agents/${agentId}?${searchParams}`}
          >
            Open project
          </Link>
        </article>
      ))}
      {company.isLoading && <div className="skeleton" />}
      {runs.length === 0 && companyId && !company.isLoading && visibleProjects.length === 0 && (
        <p className="empty">No project for this specialist matches the filter.</p>
      )}
      {runs.map((run) => (
        <article className="card" key={run.id}>
          <h2>
            {run.phase} <RunStatus status={run.status} />
          </h2>
          <p>{run.status_detail}</p>
          {agentId === "mutombo" && run.phase === "independent" && run.status !== "reviewed" && (
            <p className="badge independence">Comparison access is locked until this first pass is sealed.</p>
          )}
          <Link to={`/companies/${companyId}/agents/${agentId}/runs/${run.id}`}>Run detail</Link>
        </article>
      ))}
      {artifacts.map((artifact) => (
        <ArtifactBody key={artifact.id} kind={artifact.kind} content={artifact.content} sealed={artifact.sealed_at} sha={artifact.sha256} />
      ))}
    </>
  );
}

function ArtifactBody({
  kind,
  content,
  sealed,
  sha,
}: {
  kind: string;
  content: Record<string, unknown>;
  sealed: string | null;
  sha: string;
}) {
  const lenses = Array.isArray(content.lenses) ? content.lenses : [];
  const scenario = content.scenario as { cases?: { exit_equity: string; gross_proceeds: string; gross_moic: string }[]; limitations?: string[] } | undefined;
  return (
    <article className="card">
      <h2>{kind}</h2>
      {sealed && <p className="badge independence">Sealed {sealed}</p>}
      <p>{String(content.summary ?? "")}</p>
      {lenses.length > 0 && (
        <div className="lens-grid">
          {lenses.map((lens) => {
            const row = lens as { lens: string; score: number | null; status: string };
            return (
              <div className="lens" key={row.lens}>
                <span className="kicker">{row.lens}</span>
                <strong>{row.score ?? "—"}</strong>
                <span className="meta">{row.status.replaceAll("_", " ")}</span>
              </div>
            );
          })}
        </div>
      )}
      {scenario?.cases && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Exit equity</th>
                <th>Gross proceeds</th>
                <th>Gross MOIC</th>
              </tr>
            </thead>
            <tbody>
              {scenario.cases.map((item) => (
                <tr key={item.exit_equity}>
                  <td>{item.exit_equity}</td>
                  <td>{item.gross_proceeds}</td>
                  <td>{item.gross_moic}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul>
            {(scenario.limitations ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="hash">{sha}</p>
    </article>
  );
}
