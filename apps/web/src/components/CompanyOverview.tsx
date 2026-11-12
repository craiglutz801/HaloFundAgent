export function CompanyOverview({
  industry,
  summary,
  revenueNote,
  headcountNote,
  trajectory,
}: {
  industry: string;
  summary: string;
  revenueNote: string;
  headcountNote: string;
  trajectory: string;
}) {
  if (!industry && !summary && !revenueNote && !headcountNote && !trajectory) return null;
  return (
    <section className="company-overview" aria-label="Company overview">
      <ul>
        {industry ? (
          <li>
            <strong>Industry.</strong> {industry}
          </li>
        ) : null}
        {summary ? <li>{summary}</li> : null}
        {(revenueNote || headcountNote) && (
          <li>
            <strong>Scale.</strong> {[revenueNote, headcountNote].filter(Boolean).join(" ")}
          </li>
        )}
        {trajectory ? (
          <li>
            <strong>Trajectory.</strong> {trajectory}
          </li>
        ) : null}
      </ul>
    </section>
  );
}
