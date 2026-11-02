import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ValueStatus } from "../components/ValueStatus";

type Ledger = {
  entries: {
    id: string;
    company_name: string;
    agent_name: string;
    metric: string;
    amount: string | null;
    unit: string;
    classification: string;
    method: string;
  }[];
  gaps: { company_id: string; company_name: string; metric: string; reason: string }[];
  total: null;
};

export function ValueLedger({ principalId }: { principalId: string }) {
  const query = useQuery({
    queryKey: ["value", principalId],
    queryFn: () => api<Ledger>("/api/v1/value"),
  });
  if (query.isLoading) return <div className="skeleton" />;
  const data = query.data;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Value</h1>
          <p>Observed activity, estimated capacity, and missing money claims stay in separate rows. There is no combined total.</p>
        </div>
      </header>
      <div className="table-wrap card">
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Source</th>
              <th>Result</th>
              <th>Method</th>
            </tr>
          </thead>
          <tbody>
            {data?.entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.company_name}</td>
                <td>{entry.agent_name}</td>
                <td>
                  <ValueStatus classification={entry.classification} amount={entry.amount} unit={entry.unit} />
                  <div className="meta">{entry.metric}</div>
                </td>
                <td>{entry.method}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.entries.length === 0 && <p className="empty">No value entries are visible.</p>}
      </div>
      <section style={{ marginTop: 16 }}>
        <h2>Unavailable</h2>
        {data?.gaps.map((gap) => (
          <p key={`${gap.company_id}-${gap.metric}`}>
            <span className="badge unknown">{gap.metric.replaceAll("_", " ")}</span> {gap.company_name}: {gap.reason}
          </p>
        ))}
        <p className="meta">Combined value created: {data?.total === null ? "not reported" : "unexpected"}</p>
      </section>
    </>
  );
}
