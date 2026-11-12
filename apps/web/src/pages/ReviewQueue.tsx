import { Link, useSearchParams } from "react-router-dom";
import { useOverview } from "../api/queries";
import { formatWhen } from "../api/types";
import { FilterBar } from "../components/FilterBar";

export function ReviewQueue({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const query = useOverview(principalId, params.toString());
  if (query.isLoading) return <div className="skeleton" />;
  const decisions = query.data?.decisions ?? [];
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">Today</p>
          <h1>Review</h1>
          <p>Packets you are allowed to decide. A reviewer who cannot decide does not see the action.</p>
        </div>
      </header>
      <FilterBar />
      <section className="card queue" aria-label="Packets">
        {decisions.length === 0 && <p className="empty">No packet is waiting for your authority.</p>}
        {decisions.map((item) => (
          <div className="decision" key={item.packet_id}>
            <div>
              <strong>{item.company_name}</strong>
              <div className="muted">{item.reason}</div>
              <div className="meta">Due {formatWhen(item.due_at)}</div>
            </div>
            <Link className="button" to={`/review/packets/${item.packet_id}`}>
              Open packet
            </Link>
          </div>
        ))}
      </section>
    </>
  );
}
