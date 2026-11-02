import { useState } from "react";
import { Link, useParams } from "react-router-dom";
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
  const query = useCompany(principalId, companyId);
  const client = useQueryClient();
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [gaps, setGaps] = useState<{ kind: string; label: string }[]>([]);
  if (query.isLoading) return <div className="skeleton" />;
  if (query.isError) return <p className="empty">This company is not in your workspaces.</p>;
  if (!query.data) return null;
  const data = query.data;
  const initial = data.cases.find((item) => item.case_type === "initial") ?? data.cases[0];
  const reviewArtifact = data.artifacts.find((item) => item.id === reviewId);
  return (
    <>
      <CompanyHeader
        name={data.company.display_name}
        legalName={data.company.legal_name}
        stage={data.company.stage}
        owner={data.company.owner_name}
      />
      <StageTimeline stage={data.company.stage} />
      <div className="row-actions">
        {data.company.stage === "diligence" && hasCapability(me, "case.submit_ic") && initial && (
          <button
            className="button"
            type="button"
            onClick={async () => {
              setError("");
              try {
                await postStageAction(initial.id, {
                  action: "submit_ic",
                  rationale: "Submit the current diligence case to investment committee.",
                  expected_case_version: initial.row_version,
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
        {data.company.stage === "discovered" && hasCapability(me, "ic.decide") && initial && (
          <button
            className="button secondary"
            type="button"
            onClick={async () => {
              await postStageAction(initial.id, {
                action: "accept_first_look",
                rationale: "Partner accepts a first look on the sourced profile.",
                expected_case_version: initial.row_version,
              });
              await client.invalidateQueries();
            }}
          >
            Accept first look
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
