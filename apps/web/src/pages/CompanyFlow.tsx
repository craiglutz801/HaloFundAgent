import { Link, useSearchParams } from "react-router-dom";
import { useCompanies } from "../api/queries";
import { PHASES, phaseLabel, type CompanyCard } from "../api/types";

const OUTCOMES = [
  ["", "Open"],
  ["passed", "Passed"],
  ["portfolio", "Portfolio"],
] as const;

export function CompanyFlow({ principalId }: { principalId: string }) {
  const [params] = useSearchParams();
  const query = useCompanies(principalId, params.toString());
  const outcome = params.get("outcome") ?? "";
  if (query.isLoading) return <div className="skeleton" />;
  const items = query.data?.items ?? [];
  const counts = query.data?.counts;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Companies</h1>
          <p>Each card is one investment process. A company can have more than one.</p>
        </div>
        <div className="row-actions" role="tablist" aria-label="Outcome">
          {OUTCOMES.map(([value, label]) => (
            <OutcomeTab key={label} value={value} label={label} current={outcome} />
          ))}
        </div>
      </header>
      {counts && (
        <p className="meta">
          {counts.distinct_companies} companies · {counts.processes} processes
        </p>
      )}
      {items.length === 0 && <p className="empty">No companies match this view.</p>}
      {outcome === "" && (
        <div className="columns">
          {PHASES.map((phase) => (
            <section className="column" key={phase}>
              <h2>{phaseLabel(phase)}</h2>
              {items
                .filter((company) => company.phase === phase)
                .map((company) => (
                  <CompanyTile key={company.process_id ?? company.id} company={company} />
                ))}
            </section>
          ))}
        </div>
      )}
      {outcome !== "" &&
        items.map((company) => <CompanyTile key={company.process_id ?? company.id} company={company} />)}
    </>
  );
}

function OutcomeTab({ value, label, current }: { value: string; label: string; current: string }) {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  if (value) next.set("outcome", value);
  else next.delete("outcome");
  const search = next.toString();
  return (
    <Link className={current === value ? "button" : "button secondary"} to={search ? `/companies?${search}` : "/companies"}>
      {label}
    </Link>
  );
}

function CompanyTile({ company }: { company: CompanyCard }) {
  const [params] = useSearchParams();
  const search = params.toString();
  return (
    <Link className="card company-card" to={search ? `/companies/${company.id}?${search}` : `/companies/${company.id}`}>
      <strong>{company.display_name}</strong>
      <div className="meta">
        {company.owner_name}
        {company.case_type === "follow_on" ? " · Follow on" : ""}
      </div>
      {company.phase_label && company.outcome === "portfolio" && <div className="meta">{company.phase_label}</div>}
      {(company.active_agents ?? []).length > 0 && <div className="meta">{company.active_agents?.join(" · ")}</div>}
      {company.open_blocking_concerns > 0 && (
        <div className="badge blocking">{company.open_blocking_concerns} blocking</div>
      )}
    </Link>
  );
}
