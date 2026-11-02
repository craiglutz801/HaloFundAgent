import type { Evidence } from "../api/types";
import { formatWhen } from "../api/types";

export function EvidenceDrawer({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <p className="kicker">Source</p>
        <h2 id="evidence-title">{evidence.document?.filename ?? evidence.kind}</h2>
        <p>{evidence.excerpt}</p>
        <p className="meta">Locator {JSON.stringify(evidence.locator)}</p>
        <p className="meta">Collected {formatWhen(evidence.collected_at)}</p>
        <p className="meta">
          Observed {formatWhen(evidence.observed_start)} – {formatWhen(evidence.observed_end)}
        </p>
        <p className="meta">Sample {evidence.sample_size || "not stated"}</p>
        <p className="meta">Origin {evidence.origin_class}</p>
        {evidence.document && <p className="hash">SHA-256 {evidence.document.sha256}</p>}
        {evidence.limitations.length > 0 && (
          <ul>
            {evidence.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        <button className="button secondary" type="button" onClick={onClose}>
          Close
        </button>
      </aside>
    </div>
  );
}
