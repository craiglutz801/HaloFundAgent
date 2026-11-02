import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { formatWhen } from "../api/types";
import { MetricFreshness } from "../components/MetricFreshness";

type PortfolioView = {
  companies: { company_id: string; display_name: string; health: string; reason: string }[];
  synced_at: string;
};

export function Portfolio({ principalId }: { principalId: string }) {
  const query = useQuery({
    queryKey: ["portfolio", principalId],
    queryFn: () => api<PortfolioView>("/api/v1/portfolio"),
  });
  if (query.isLoading) return <div className="skeleton" />;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Portfolio</h1>
          <p>Owned companies only. Unknown wins when required reporting is missing or stale.</p>
        </div>
        <p className="meta">Synced {formatWhen(query.data?.synced_at)}</p>
      </header>
      {(query.data?.companies ?? []).map((company) => (
        <article className="card" key={company.company_id}>
          <h2>
            <Link to={`/companies/${company.company_id}`}>{company.display_name}</Link>
          </h2>
          <MetricFreshness health={company.health} reason={company.reason} />
        </article>
      ))}
      {query.data?.companies.length === 0 && <p className="empty">No owned companies are in your workspaces.</p>}
    </>
  );
}
