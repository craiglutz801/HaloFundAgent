import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { postStageAction } from "../api/generated";
import { useCompany } from "../api/queries";
import type { Evidence, Me } from "../api/types";
import { hasCapability } from "../api/types";
import { CompanyHeader } from "../components/CompanyHeader";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { ReviewDialog } from "../components/ReviewDialog";
import { StageTimeline } from "../components/StageTimeline";
import { WorkstreamTrack } from "../components/WorkstreamTrack";

export function CompanyWorkspace({ principalId, me }: { principalId: string; me: Me }) {
  const { companyId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const query = useCompany(principalId, companyId, params.toString());
  const companyFilter = params.get("company");
  const client = useQueryClient();
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [gaps, setGaps] = useState<{ kind: string; label: string }[]>([]);
  if (query.isLoading) return <div className="skeleton" />;
  if (query.isError) return <p className="empty">This company is not in your workspaces.</p>;
  if (companyFilter && companyFilter !== companyId) {
    return (
      <p className="empty">
        This company is outside the company filter.
        <button
          className="button secondary"
          type="button"
          onClick={() => {
            const next = new URLSearchParams(params);
            next.delete("company");
            setParams(next);
          }}
        >
          Clear the company filter
        </button>
      </p>
    );
  }
  if (!query.data) return null;
  const data = query.data;
  const primary = data.cases.find((item) => item.primary) ?? data.cases.find((item) => item.case_type === "initial") ?? data.cases[0];
  const openProcess = data.cases.find((item) => item.outcome === "open") ?? primary;
  const otherOpen =
    primary && openProcess && openProcess.id !== primary.id
      ? `Open ${openProcess.case_type.replaceAll("_", " ")} in ${openProcess.phase_label ?? openProcess.phase}`
      : undefined;
  const reviewArtifact = data.artifacts.find((item) => item.id === reviewId);
  return (
    <>
      <CompanyHeader
        name={data.company.display_name}
        legalName={data.company.legal_name}
        phase={primary?.phase ?? "unknown"}
        outcome={primary?.outcome ?? "open"}
        owner={data.company.owner_name}
        otherOpen={otherOpen}
      />
      <StageTimeline phase={primary?.phase ?? ""} />
      <div className="row-actions">
        {openProcess?.phase === "due_diligence" && hasCapability(me, "case.submit_ic") && (
          <button
            className="button"
            type="button"
            onClick={async () => {
              setError("");
              try {
                await postStageAction(openProcess.id, {
                  action: "submit_ic",
                  rationale: "Submit the current diligence case to investment committee.",
                  expected_case_version: openProcess.row_version,
                });
                await client.invalidateQueries();
              } catch (caught) {
                if (caught instanceof ApiError) {
                  setError(caught.message);
                  const missing = caught.details.missing_requirements;
                  setGaps(Array.isArray(missing) ? (missing as { kind: string; label: string }[]) : []);
                }
              }
            }}
          >
            Submit to IC
          </button>
        )}
        {openProcess?.phase === "sourcing" && hasCapability(me, "ic.decide") && (
          <button
            className="button secondary"
            type="button"
            onClick={async () => {
              await postStageAction(openProcess.id, {
                action: "accept_first_look",
                rationale: "Partner accepts a first look on the sourced profile.",
                expected_case_version: openProcess.row_version,
              });
              await client.invalidateQueries();
            }}
          >
            Accept into screening
          </button>
        )}
        {openProcess?.phase === "term_sheet" && hasCapability(me, "ic.decide") && (
          <button
            className="button secondary"
            type="button"
            onClick={async () => {
              await postStageAction(openProcess.id, {
                action: "advance_closing",
                rationale: "Open negotiation and closing from the approved term sheet.",
                expected_case_version: openProcess.row_version,
              });
              await client.invalidateQueries();
            }}
          >
            Open closing
          </button>
        )}
        {openProcess?.phase === "negotiation_closing" && hasCapability(me, "ic.decide") && (
          <button
            className="button"
            type="button"
            onClick={async () => {
              await postStageAction(openProcess.id, {
                action: "confirm_close",
                rationale: "Confirm the close. This is the step that creates the portfolio record.",
                expected_case_version: openProcess.row_version,
              });
              await client.invalidateQueries();
            }}
          >
            Confirm close
          </button>
        )}
      </div>
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
      {data.filter_restricted && (data.assignments ?? []).length === 0 && (
        <p className="empty">No projects on this company match the current filter.</p>
      )}
      <section>
        <h2>Projects</h2>
        <div className="stack">
          {(data.assignments ?? []).length === 0 && !data.filter_restricted && (
            <p className="empty">No agent projects on this company yet.</p>
          )}
          {(data.assignments ?? []).map((assignment) => (
            <article className="card" key={assignment.id}>
              <p className="kicker">{assignment.agent_name}</p>
              <h3>{assignment.title}</h3>
              <p>{assignment.objective}</p>
              <p className="meta">
                {assignment.status.replaceAll("_", " ")}
                {assignment.working_now ? " · working now" : ""}
                {assignment.working_state === "unknown" ? " · working state unknown" : ""}
                {assignment.phase_label ? ` · ${assignment.phase_label}` : ""}
              </p>
              <Link to={`/companies/${data.company.id}/agents/${assignment.agent_id}${params.toString() ? `?${params}` : ""}`}>
                Open {assignment.agent_name}
              </Link>
            </article>
          ))}
        </div>
      </section>
      <div className="grid two">
        <section>
          <h2>Workstreams</h2>
          <div className="tracks">
            {data.runs.length === 0 && <p className="empty">No specialist run yet.</p>}
            {data.runs.map((run) => (
              <WorkstreamTrack
                key={run.id}
                companyId={data.company.id}
                agent={run.agent_name}
                phase={run.phase}
                status={run.status}
                detail={run.status_detail}
              />
            ))}
          </div>
        </section>
        <section>
          <h2>Concerns</h2>
          {data.concerns.length === 0 && <p className="empty">No concerns on this company.</p>}
          {data.concerns.map((concern) => (
            <article className="card" key={concern.id}>
              <span className={concern.blocking ? "badge blocking" : "badge"}>{concern.status}</span>
              <h3>{concern.question}</h3>
              <p className="meta">Owner {concern.owner_name}</p>
            </article>
          ))}
        </section>
      </div>
      <section style={{ marginTop: 16 }}>
        <h2>Evidence</h2>
        <div className="stack">
          {data.evidence.map((item) => (
            <button className="card" key={item.id} type="button" onClick={() => setEvidence(item)} style={{ textAlign: "left" }}>
              <strong>{item.document?.filename}</strong>
              <div className="meta">{item.kind}</div>
            </button>
          ))}
        </div>
      </section>
      <section style={{ marginTop: 16 }}>
        <h2>Drafts</h2>
        {data.artifacts.map((artifact) => (
          <article className="card" key={artifact.id}>
            <h3>{artifact.kind}</h3>
            <p className="hash">{artifact.sha256}</p>
            <div className="row-actions">
              {hasCapability(me, "artifact.review") && (
                <button className="button secondary" type="button" onClick={() => setReviewId(artifact.id)}>
                  Review draft
                </button>
              )}
              <Link to={`/companies/${data.company.id}/agents/${artifact.kind.startsWith("mutombo") || artifact.kind === "independent_risk_report" ? "mutombo" : artifact.kind.split("_")[0]}`}>
                Open specialist
              </Link>
            </div>
          </article>
        ))}
      </section>
      {data.packets.filter((packet) => packet.status === "frozen").map((packet) => (
        <p key={packet.id}>
          <Link className="button" to={`/review/packets/${packet.id}`}>
            Open frozen packet
          </Link>
        </p>
      ))}
      {evidence && <EvidenceDrawer evidence={evidence} onClose={() => setEvidence(null)} />}
      {reviewArtifact && (
        <ReviewDialog
          artifact={reviewArtifact}
          onClose={() => setReviewId(null)}
          onSaved={() => {
            setReviewId(null);
            void client.invalidateQueries();
          }}
        />
      )}
    </>
  );
}
