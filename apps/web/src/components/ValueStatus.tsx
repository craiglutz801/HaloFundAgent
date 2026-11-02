export function ValueStatus({ classification, amount, unit }: { classification: string; amount: string | null; unit: string }) {
  return (
    <span className={`badge ${classification}`}>
      {classification} {amount ?? "—"} {unit}
    </span>
  );
}
