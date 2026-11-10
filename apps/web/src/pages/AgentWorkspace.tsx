import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getAgents } from "../api/generated";
import { filterQuery, useCompany } from "../api/queries";
import type { Artifact } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { ReviewDialog } from "../components/ReviewDialog";
import { RunStatus } from "../components/RunStatus";
import { StageActions } from "../components/StageActions";
import { WorkProduct } from "../components/WorkProduct";
import { useHalo } from "../session";

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
          projects: {
            id: string;
            company_id: string;
            company_name: string;
            title: string;
            status: string;
            objective: string;
            insight?: string;
            recommendation?: string;
            next_step?: string;
          }[];
        }[];
      }>,
    enabled: !companyId,
  });
  const { me } = useHalo();
  const client = useQueryClient();
  const [review, setReview] = useState<Artifact | null>(null);
  const [error, setError] = useState("");
  const [gaps, setGaps] = useState<{ kind: string; label: string }[]>([]);
  const profile = COPY[agentId] ?? { name: agentId, job: "" };
  const runs = (company.data?.runs ?? []).filter((run) => run.agent_name === agentId);
  const projects = directory.data?.agents.find((agent) => agent.id === agentId)?.projects ?? [];
  const visibleProjects = companyId
    ? (company.data?.assignments ?? []).filter((item) => item.agent_id === agentId)
    : projects;
  const artifacts = company.data?.artifacts.filter((artifact) => runs.some((run) => run.id === artifact.run_id)) ?? [];
  const openProcess =
    company.data?.cases.find((item) => item.outcome === "open") ??
    company.data?.cases.find((item) => item.primary) ??
    company.data?.cases[0];
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">{company.data?.company.display_name ?? "Specialist"}</p>
          <h1>{profile.name}</h1>
          <p>{profile.job}</p>
        </div>
      </header>
      <FilterBar />
      {!companyId && projects.length === 0 && !directory.isLoading && (
        <p className="empty">No projects match this filter.</p>
      )}
      {!companyId && projects.length > 0 && (
        <div className="stack-gap">
          {projects.map((project) => (
            <article className="card agent-brief" key={project.id}>
              <div>
                <p className="kicker">{project.company_name}</p>
                <h2>{project.title}</h2>
                <p className="insight">{project.insight || project.objective}</p>
                {project.recommendation && <p>{project.recommendation}</p>}
                {project.next_step && <p className="next-step">Next step · {project.next_step}</p>}
              </div>
              <div className="roster-side">
                <span className="meta">{project.status.replaceAll("_", " ")}</span>
                <Link className="button" to={`/companies/${project.company_id}/agents/${agentId}?${searchParams}`}>
                  Open the work
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
      {company.isLoading && <div className="skeleton" />}
      {companyId && !company.isLoading && (
        <>
          {error && <p className="error">{error}</p>}
          {gaps.length > 0 && (
            <ul>
              {gaps.map((gap) => (
                <li key={gap.label}>
                  {gap.kind}: {gap.label}
                </li>
              ))}
            </ul>
          )}
          <div className="row-actions">
            <StageActions me={me} openProcess={openProcess} onError={setError} onGaps={setGaps} />
            <Link className="button secondary" to={`/companies/${companyId}?${searchParams}`}>
              Company
            </Link>
          </div>
          {runs.length === 0 && visibleProjects.length === 0 && (
            <p className="empty">No project for this specialist matches the filter.</p>
          )}
          {artifacts.map((artifact) => (
            <article className="card" key={artifact.id}>
              <div className="dossier-head">
                <div>
                  <p className="kicker">{artifact.kind.replaceAll("_", " ")}</p>
                  <RunStatus status={artifact.status} />
                </div>
                {artifact.status !== "reviewed" && artifact.status !== "sealed" && (
                  <button className="button" type="button" onClick={() => setReview(artifact)}>
                    Review draft
                  </button>
                )}
              </div>
              {agentId === "mutombo" && artifact.phase === "independent" && artifact.status !== "reviewed" && artifact.sealed_at == null && (
                <p className="badge independence">Comparison access is locked until this first pass is sealed.</p>
              )}
              <WorkProduct content={artifact.content} />
              <ArtifactExtras content={artifact.content} />
              <p className="hash">{artifact.sha256}</p>
            </article>
          ))}
          {artifacts.length === 0 &&
            runs.map((run) => (
              <article className="card" key={run.id}>
                <h2>
                  {run.phase} <RunStatus status={run.status} />
                </h2>
                <p>{run.status_detail}</p>
              </article>
            ))}
        </>
      )}
      {review && (
        <ReviewDialog
          artifact={review}
          onClose={() => setReview(null)}
          onSaved={() => {
            setReview(null);
            void client.invalidateQueries();
          }}
        />
      )}
    </>
  );
}

function ArtifactExtras({ content }: { content: Record<string, unknown> }) {
  const lenses = Array.isArray(content.lenses) ? content.lenses : [];
  const scenario = content.scenario as { cases?: { exit_equity: string; gross_proceeds: string; gross_moic: string }[]; limitations?: string[] } | undefined;
  if (lenses.length === 0 && !scenario?.cases) return null;
  return (
    <div>
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
    </div>
  );
}
