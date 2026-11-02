import { useState } from "react";
import { ApiError } from "../api/client";
import { postReview } from "../api/generated";
import type { Artifact } from "../api/types";
import { Dialog } from "./Dialog";

export function ReviewDialog({
  artifact,
  onClose,
  onSaved,
}: {
  artifact: Artifact;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [verdict, setVerdict] = useState("approve_draft");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  return (
    <Dialog title="Review this draft" onClose={onClose}>
      <p className="meta">
        Version {artifact.version} · {artifact.kind}
      </p>
      <p className="hash">{artifact.sha256}</p>
      <p className="muted">A review records your assessment of these bytes. It does not clear concerns or approve an investment.</p>
      <label htmlFor="verdict">Verdict</label>
      <select id="verdict" className="field" value={verdict} onChange={(event) => setVerdict(event.target.value)}>
        <option value="approve_draft">Approve draft</option>
        <option value="request_changes">Request changes</option>
        <option value="reject_unsupported">Reject unsupported output</option>
      </select>
      <label htmlFor="notes">Notes</label>
      <textarea id="notes" rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} />
      {error && <p className="error">{error}</p>}
      <div className="row-actions">
        <button
          className="button"
          type="button"
          onClick={async () => {
            try {
              await postReview(artifact.id, { artifact_sha256: artifact.sha256, verdict, notes });
              onSaved();
            } catch (caught) {
              setError(caught instanceof ApiError ? caught.message : "Review failed");
            }
          }}
        >
          Record review
        </button>
        <button className="button secondary" type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Dialog>
  );
}
