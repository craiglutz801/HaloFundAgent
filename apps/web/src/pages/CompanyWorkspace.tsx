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
import { FilterBar } from "../components/FilterBar";
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
  const search = params.toString();
  return (
    <>
      <CompanyHeader
        name={data.company.display_name}
        legalName={data.company.legal_name}
        phase={primary?.phase ?? "unknown"}
        outcome={primary?.outcome ?? "open"}
        owner={data.company.owner_name}
        otherOpen={otherOpen}
        actions={<StageActions me={me} openProcess={openProcess} onError={setError} onGaps={setGaps} />}
      />
      <StageTimeline phase={primary?.phase ?? ""} />
      <FilterBar />
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
      <div className="deal">
        <div className="deal-main">
          <section className="card">
            <h2 className="panel-title">Projects</h2>
            <div className="roster">
              {(data.assignments ?? []).length === 0 && !data.filter_restricted && (
                <p className="empty">No agent projects on this company yet.</p>
              )}
              {(data.assignments ?? []).map((assignment) => (
                <div className="roster-row" key={assignment.id}>
                  <div>
                    <p className="kicker">{assignment.agent_name}</p>
                    <strong>{assignment.title}</strong>
                    <p className="muted">{assignment.objective}</p>
                  </div>
                  <div className="roster-side">
                    <span className="meta">
                      {assignment.status.replaceAll("_", " ")}
                      {assignment.working_now ? " · working now" : ""}
                      {assignment.working_state === "unknown" ? " · working state unknown" : ""}
                    </span>
                    <Link to={`/companies/${data.company.id}/agents/${assignment.agent_id}${search ? `?${search}` : ""}`}>
                      Open
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>
          {data.runs.length > 0 && (
            <section>
              <h2>Runs</h2>
              <div className="tracks">
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
          )}
        </div>
        <aside className="deal-side">
          <section className="card">
            <h2 className="panel-title">Concerns</h2>
            {data.concerns.length === 0 && <p className="empty">No concerns on this company.</p>}
            {data.concerns.map((concern) => (
              <div className="decision" key={concern.id}>
                <div>
                  <span className={concern.blocking ? "badge blocking" : "badge"}>{concern.status}</span>
                  <div className="muted">{concern.question}</div>
                  <div className="meta">Owner {concern.owner_name}</div>
                </div>
              </div>
            ))}
          </section>
          <section className="card">
            <h2 className="panel-title">Evidence</h2>
            {data.evidence.length === 0 && <p className="empty">No evidence on file.</p>}
            <div className="roster">
              {data.evidence.map((item) => (
                <button className="roster-row" key={item.id} type="button" onClick={() => setEvidence(item)}>
                  <div>
                    <strong>{item.document?.filename}</strong>
                    <div className="meta">{item.kind}</div>
                  </div>
                </button>
              ))}
            </div>
          </section>
          <section className="card">
            <h2 className="panel-title">Drafts</h2>
            {data.artifacts.length === 0 && <p className="empty">No drafts yet.</p>}
            {data.artifacts.map((artifact) => (
              <div className="decision" key={artifact.id}>
                <div>
                  <strong>{artifact.kind.replaceAll("_", " ")}</strong>
                  <p className="hash">{artifact.sha256}</p>
                </div>
                {hasCapability(me, "artifact.review") && (
                  <button className="button secondary" type="button" onClick={() => setReviewId(artifact.id)}>
                    Review
                  </button>
                )}
              </div>
            ))}
          </section>
          {data.packets
            .filter((packet) => packet.status === "frozen")
            .map((packet) => (
              <Link key={packet.id} className="button" to={`/review/packets/${packet.id}`}>
                Open frozen packet
              </Link>
            ))}
        </aside>
      </div>
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

function StageActions({
  me,
  openProcess,
  onError,
  onGaps,
}: {
  me: Me;
  openProcess: { id: string; phase?: string; row_version: number } | undefined;
  onError: (message: string) => void;
  onGaps: (gaps: { kind: string; label: string }[]) => void;
}) {
  const client = useQueryClient();
  if (!openProcess) return null;
  async function act(action: string, rationale: string) {
    if (!openProcess) return;
    onError("");
    onGaps([]);
    try {
      await postStageAction(openProcess.id, {
        action,
        rationale,
        expected_case_version: openProcess.row_version,
      });
      await client.invalidateQueries();
    } catch (caught) {
      if (caught instanceof ApiError) {
        onError(caught.message);
        const missing = caught.details.missing_requirements;
        onGaps(Array.isArray(missing) ? (missing as { kind: string; label: string }[]) : []);
      }
    }
  }
  return (
    <div className="row-actions">
      {openProcess.phase === "due_diligence" && hasCapability(me, "case.submit_ic") && (
        <button className="button" type="button" onClick={() => void act("submit_ic", "Submit the current diligence case to investment committee.")}>
          Submit to IC
        </button>
      )}
      {openProcess.phase === "sourcing" && hasCapability(me, "ic.decide") && (
        <button className="button secondary" type="button" onClick={() => void act("accept_first_look", "Partner accepts a first look on the sourced profile.")}>
          Accept into screening
        </button>
      )}
      {openProcess.phase === "term_sheet" && hasCapability(me, "ic.decide") && (
        <button className="button secondary" type="button" onClick={() => void act("advance_closing", "Open negotiation and closing from the approved term sheet.")}>
          Open closing
        </button>
      )}
      {openProcess.phase === "negotiation_closing" && hasCapability(me, "ic.decide") && (
        <button className="button" type="button" onClick={() => void act("confirm_close", "Confirm the close. This is the step that creates the portfolio record.")}>
          Confirm close
        </button>
      )}
    </div>
  );
}
