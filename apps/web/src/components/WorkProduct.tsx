type Dive = { label?: string; detail?: string };
type Finding = { statement?: string };

export function WorkProduct({ content }: { content: Record<string, unknown> }) {
  const insight = text(content.insight) || text(content.summary);
  const summary = text(content.summary);
  const recommendation = text(content.recommendation);
  const nextStep = text(content.next_step);
  const worked = strings(content.worked);
  const dives = Array.isArray(content.deep_dive) ? (content.deep_dive as Dive[]) : [];
  const findings = Array.isArray(content.findings) ? (content.findings as Finding[]) : [];
  const questions = strings(content.human_questions);
  const actions = strings(content.proposed_actions);
  const missing = strings(content.missing_evidence);
  if (!insight && worked.length === 0 && dives.length === 0 && findings.length === 0) {
    return <p className="empty">No brief is on this run yet.</p>;
  }
  return (
    <div className="work">
      {insight && <p className="insight">{insight}</p>}
      {summary && summary !== insight && <p className="muted">{summary}</p>}
      {worked.length > 0 && (
        <section>
          <h3>What happened</h3>
          <ol className="steps">
            {worked.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </section>
      )}
      {dives.length > 0 && (
        <section>
          <h3>Deep dive</h3>
          <div className="deep-grid">
            {dives.map((dive) => (
              <article key={dive.label} className="deep">
                <p className="kicker">{dive.label}</p>
                <p>{dive.detail}</p>
              </article>
            ))}
          </div>
        </section>
      )}
      {findings.length > 0 && (
        <section>
          <h3>Findings</h3>
          <ul className="findings">
            {findings.map((finding) => (
              <li key={finding.statement}>{finding.statement}</li>
            ))}
          </ul>
        </section>
      )}
      {missing.length > 0 && (
        <p className="meta">Missing: {missing.join(" ")}</p>
      )}
      {questions.length > 0 && (
        <section>
          <h3>Questions for a person</h3>
          <ul className="findings">
            {questions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}
      {(recommendation || actions.length > 0 || nextStep) && (
        <section className="recommend">
          <h3>Recommendation</h3>
          {recommendation && <p>{recommendation}</p>}
          {actions.map((item) => (
            <p key={item}>{item}</p>
          ))}
          {nextStep && <p className="next-step">Next step · {nextStep}</p>}
        </section>
      )}
    </div>
  );
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function strings(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
