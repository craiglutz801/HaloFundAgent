import { Link, useSearchParams } from "react-router-dom";
import { useOverview } from "../api/queries";
import { formatWhen } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { MetricFreshness } from "../components/MetricFreshness";
import { PhaseIndex } from "../components/PhaseIndex";

export function Overview({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const query = useOverview(principalId, params.toString());
  if (query.isLoading) return <div className="skeleton" />;
  if (!query.data) return <p className="empty">Overview is unavailable.</p>;
  const data = query.data;
  const waiting = data.decisions.length;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">Today</p>
          <h1>{waiting === 0 ? "Nothing is waiting on you" : `${waiting} decision${waiting === 1 ? "" : "s"} need you`}</h1>
          <p>Open the packet. The specialist transcript is not the decision.</p>
        </div>
        <p className="meta">Synced {formatWhen(data.synced_at)}</p>
      </header>
      <FilterBar />
      <section className="card queue" aria-label="Decisions">
        {waiting === 0 && <p className="empty">Nothing in your authority is waiting.</p>}
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
      </section>
      <PhaseIndex counts={data.stage_counts} />
      <div className="grid two">
        <section className="card">
          <h2 className="panel-title">Blocked</h2>
          {data.blockers.length === 0 && <p className="empty">No open blocking concern.</p>}
          {data.blockers.map((item) => (
            <div className="decision" key={item.concern_id}>
              <div>
                <strong>{item.company_name}</strong>
                <div className="muted">{item.question}</div>
                <div className="meta">
                  <span className="badge blocking">{item.severity}</span> {item.owner_name}
                </div>
              </div>
              <Link to={`/companies/${item.company_id}`}>Open</Link>
            </div>
          ))}
        </section>
        <section className="card">
          <h2 className="panel-title">Portfolio</h2>
          {data.portfolio_attention.length === 0 && <p className="empty">No owned company needs attention.</p>}
          {data.portfolio_attention.map((item) => (
            <div className="decision" key={item.company_id}>
              <div>
                <strong>{item.company_name}</strong>
                <MetricFreshness health={item.health} reason={item.reason} />
              </div>
              <Link to={`/companies/${item.company_id}`}>Open</Link>
            </div>
          ))}
          {data.notifications.map((item) => (
            <p key={item.id}>
              <span className="badge unknown">{item.severity}</span> {item.title}. {item.body}
            </p>
          ))}
        </section>
      </div>
    </>
  );
}
