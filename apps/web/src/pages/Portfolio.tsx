import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getPortfolio } from "../api/generated";
import { filterQuery } from "../api/queries";
import { formatWhen } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { MetricFreshness } from "../components/MetricFreshness";

type PortfolioView = {
  companies: { company_id: string; display_name: string; health: string; reason: string }[];
  synced_at: string;
};

export function Portfolio({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const search = params.toString();
  const query = useQuery({
    queryKey: ["portfolio", principalId, search],
    queryFn: () => getPortfolio(filterQuery(search)) as Promise<PortfolioView>,
  });
  if (query.isLoading) return <div className="skeleton" />;
  const companies = query.data?.companies ?? [];
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">Pipeline</p>
          <h1>Portfolio</h1>
          <p>A confirmed close. An IC approval and a term sheet do not put a company here.</p>
        </div>
        <p className="meta">Synced {formatWhen(query.data?.synced_at)}</p>
      </header>
      <FilterBar />
      {companies.length === 0 && <p className="empty">No owned companies are in your workspaces.</p>}
      {companies.length > 0 && (
        <div className="roster card">
          {companies.map((company) => (
            <Link className="roster-row" key={company.company_id} to={search ? `/companies/${company.company_id}?${search}` : `/companies/${company.company_id}`}>
              <strong>{company.display_name}</strong>
              <MetricFreshness health={company.health} reason={company.reason} />
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
