export function FindingCard({
  statement,
  onOpenEvidence,
}: {
  statement: string;
  onOpenEvidence?: () => void;
}) {
  return (
    <article className="card">
      <h3>Finding</h3>
      <p>{statement}</p>
      {onOpenEvidence && (
        <button className="button secondary" type="button" onClick={onOpenEvidence}>
          Inspect source
        </button>
      )}
    </article>
  );
}
