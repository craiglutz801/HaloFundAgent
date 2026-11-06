import { Link, useSearchParams } from "react-router-dom";
import { useOverview } from "../api/queries";
import { formatWhen } from "../api/types";

export function ReviewQueue({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const query = useOverview(principalId, params.toString());
  if (query.isLoading) return <div className="skeleton" />;
  const decisions = query.data?.decisions ?? [];
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Review</h1>
          <p>Packets you are authorized to decide. A reviewer who cannot decide does not see this action.</p>
        </div>
      </header>
      {decisions.length === 0 && <p className="empty">No packet is waiting for your authority.</p>}
      {decisions.map((item) => (
        <article className="card" key={item.packet_id}>
          <h2>{item.company_name}</h2>
          <p>{item.reason}</p>
          <p className="meta">Due {formatWhen(item.due_at)}</p>
          <Link className="button" to={`/review/packets/${item.packet_id}`}>
            Open packet
          </Link>
        </article>
      ))}
    </>
  );
}
