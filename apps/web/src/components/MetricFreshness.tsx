export function MetricFreshness({ health, reason }: { health: string; reason: string }) {
  return (
    <p>
      <span className={`badge ${health}`}>{health.replaceAll("_", " ")}</span> {reason}
    </p>
  );
}
