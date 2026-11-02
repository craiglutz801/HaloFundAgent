export function RunStatus({ status }: { status: string }) {
  const tone = status === "reviewed" || status === "ready_for_review" ? "ready" : status === "running" ? "unknown" : "";
  return <span className={`badge ${tone}`}>{status.replaceAll("_", " ")}</span>;
}
