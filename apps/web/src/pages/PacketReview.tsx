import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { postDecision } from "../api/generated";
import { usePacket } from "../api/queries";
import { formatWhen } from "../api/types";
import { Dialog } from "../components/Dialog";

export function PacketReview({ principalId }: { principalId: string }) {
  const { packetId = "" } = useParams();
  const query = usePacket(principalId, packetId);
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [decision, setDecision] = useState("approve");
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");
  if (query.isLoading) return <div className="skeleton" />;
  if (query.isError || !query.data) return <p className="empty">This packet is not available.</p>;
  const packet = query.data;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">{packet.case.case_type.replaceAll("_", " ")}</p>
          <h1>{packet.company.display_name}</h1>
          <p>
            Company stage {packet.company.stage.replaceAll("_", " ")} · packet {packet.status}
          </p>
        </div>
        {packet.can_decide && (
          <button className="button" type="button" onClick={() => setOpen(true)}>
            Record decision
          </button>
        )}
      </header>
      <p className="hash">Manifest {packet.manifest_sha256}</p>
      <p className="meta">Policy {packet.policy_version}</p>
      {packet.decision && (
        <article className="card">
          <h2>Recorded decision: {packet.decision.decision}</h2>
          <p>{packet.decision.rationale}</p>
          <p className="meta">{formatWhen(packet.decision.decided_at)}</p>
          <p className="hash">{packet.decision.packet_sha256}</p>
        </article>
      )}
      <section>
        <h2>Concerns</h2>
        {packet.concerns.length === 0 && <p className="empty">No concerns on this case.</p>}
        {packet.concerns.map((concern) => (
          <p key={concern.id}>
            <span className={concern.blocking ? "badge blocking" : "badge"}>{concern.status}</span> {concern.question}
          </p>
        ))}
      </section>
      {packet.artifacts.map((artifact) => (
        <article className="card" key={artifact.id}>
          <h2>
            {artifact.kind} {artifact.sealed_at && <span className="badge independence">sealed dissent</span>}
          </h2>
          <p>{String(artifact.content.summary ?? "")}</p>
          <p className="hash">{artifact.sha256}</p>
        </article>
      ))}
      <Link to={`/companies/${packet.company.id}`}>Company workspace</Link>
      {open && (
        <Dialog title="Record an IC decision" onClose={() => setOpen(false)}>
          <p className="muted">This is separate from reviewing a draft. Approval moves an initial case to closing. It does not create ownership.</p>
          <label htmlFor="decision">Decision</label>
          <select id="decision" className="field" value={decision} onChange={(event) => setDecision(event.target.value)}>
            <option value="approve">Approve</option>
            <option value="pass">Pass</option>
            <option value="defer">Defer</option>
            <option value="terms_revision">Terms revision</option>
          </select>
          <label htmlFor="rationale">Rationale</label>
          <textarea id="rationale" rows={4} value={rationale} onChange={(event) => setRationale(event.target.value)} />
          {error && <p className="error">{error}</p>}
          <div className="row-actions">
            <button
              className="button"
              type="button"
              onClick={async () => {
                try {
                  await postDecision(packet.id, {
                    packet_sha256: packet.manifest_sha256,
                    decision,
                    rationale,
                    expected_case_version: packet.case.row_version,
                    policy_version: packet.policy_version,
                  });
                  setOpen(false);
                  await client.invalidateQueries();
                } catch (caught) {
                  setError(caught instanceof ApiError ? caught.message : "Decision failed");
                }
              }}
            >
              Record decision
            </button>
            <button className="button secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
