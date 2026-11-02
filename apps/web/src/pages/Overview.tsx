import { Link } from "react-router-dom";
import { useOverview } from "../api/queries";
import { formatWhen, stageLabel } from "../api/types";
import { MetricFreshness } from "../components/MetricFreshness";

export function Overview({ principalId }: { principalId: string }) {
  const query = useOverview(principalId);
  if (query.isLoading) return <div className="skeleton" />;
  if (!query.data) return <p className="empty">Overview is unavailable.</p>;
  const data = query.data;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>{data.decisions.length === 0 ? "No decisions are waiting" : `${data.decisions.length} decisions need you`}</h1>
          <p>Open a packet directly. Agent transcripts are not the review surface.</p>
        </div>
        <p className="meta">Synced {formatWhen(data.synced_at)}</p>
      </header>
      <div className="grid two">
        <section className="card">
          <h2>Decisions</h2>
          {data.decisions.length === 0 && <p className="empty">Nothing in your authority is waiting.</p>}
          <div className="stack">
            {data.decisions.map((item) => (
              <div className="decision" key={item.packet_id}>
                <div>
                  <strong>{item.company_name}</strong>
                  <div className="muted">{item.reason}</div>
                  <div className="meta">
                    {item.owner_name} · due {formatWhen(item.due_at)}
                  </div>
                </div>
                <Link className="button" to={`/review/packets/${item.packet_id}`}>
                  Open packet
                </Link>
              </div>
            ))}
          </div>
        </section>
        <section className="card">
          <h2>Blocked work</h2>
          {data.blockers.length === 0 && <p className="empty">No open blocking concerns in your workspaces.</p>}
          {data.blockers.map((item) => (
            <div className="decision" key={item.concern_id}>
              <div>
                <span className="badge blocking">{item.severity}</span>
                <div>
                  {item.company_name}: {item.question}
                </div>
                <div className="meta">Owner {item.owner_name}</div>
              </div>
              <Link to={`/companies/${item.company_id}`}>Open</Link>
            </div>
          ))}
        </section>
      </div>
      <div className="grid two" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>Portfolio attention</h2>
          {data.portfolio_attention.length === 0 && <p className="empty">No owned company needs attention.</p>}
          {data.portfolio_attention.map((item) => (
            <div key={item.company_id}>
              <strong>{item.company_name}</strong>
              <MetricFreshness health={item.health} reason={item.reason} />
            </div>
          ))}
          {data.notifications.map((item) => (
            <p key={item.id}>
              <span className="badge unknown">{item.severity}</span> {item.title}. {item.body}
            </p>
          ))}
        </section>
        <section className="card">
          <h2>Stages you can see</h2>
          {data.stage_counts
            .filter((item) => item.count > 0)
            .map((item) => (
              <div className="decision" key={item.stage}>
                <span>{stageLabel(item.stage)}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
        </section>
      </div>
    </>
  );
}
