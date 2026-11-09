import { Link, useSearchParams } from "react-router-dom";
import { useCompanies } from "../api/queries";
import { PHASES, phaseLabel, type CompanyCard } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { PhaseIndex } from "../components/PhaseIndex";

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
  const locked = params.get("phase");
  const phaseCounts = PHASES.map((phase) => ({
    stage: phase,
    count: locked && locked !== phase ? -1 : items.filter((company) => company.phase === phase).length,
  }));
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">Pipeline</p>
          <h1>Companies</h1>
          <p>One row is one investment process. A company can appear more than once.</p>
        </div>
        <div className="segmented" role="tablist" aria-label="Outcome">
          {OUTCOMES.map(([value, label]) => (
            <OutcomeTab key={label} value={value} label={label} current={outcome} />
          ))}
        </div>
      </header>
      <FilterBar />
      {counts && (
        <p className="meta tally">
          {counts.distinct_companies} companies · {counts.processes} processes
        </p>
      )}
      {outcome === "" && <PhaseIndex counts={phaseCounts} />}
      {items.length === 0 && <p className="empty">No companies match this view.</p>}
      {outcome === "" &&
        PHASES.filter((phase) => !params.get("phase") || params.get("phase") === phase).map((phase) => {
          const rows = items.filter((company) => company.phase === phase);
          if (rows.length === 0) return null;
          return (
            <section className="phase-band" key={phase}>
              <h2>
                {phaseLabel(phase)}
                <span className="count">{rows.length}</span>
              </h2>
              <div className="roster">
                {rows.map((company) => (
                  <CompanyRow key={company.process_id ?? company.id} company={company} />
                ))}
              </div>
            </section>
          );
        })}
      {outcome !== "" && (
        <div className="roster card">
          {items.map((company) => (
            <CompanyRow key={company.process_id ?? company.id} company={company} />
          ))}
        </div>
      )}
    </>
  );
}

function OutcomeTab({ value, label, current }: { value: string; label: string; current: string }) {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  if (value) next.set("outcome", value);
  else next.delete("outcome");
  next.delete("phase");
  const search = next.toString();
  return (
    <Link aria-current={current === value ? "page" : undefined} to={search ? `/companies?${search}` : "/companies"}>
      {label}
    </Link>
  );
}

function CompanyRow({ company }: { company: CompanyCard }) {
  const [params] = useSearchParams();
  const search = params.toString();
  const agents = company.active_agents ?? [];
  return (
    <Link className="roster-row" to={search ? `/companies/${company.id}?${search}` : `/companies/${company.id}`}>
      <div>
        <strong>{company.display_name}</strong>
        <div className="meta">
          {company.owner_name}
          {company.case_type === "follow_on" ? " · Follow on" : ""}
          {company.outcome && company.outcome !== "open" && company.phase_label ? ` · ${company.phase_label}` : ""}
        </div>
      </div>
      <div className="roster-side">
        {agents.length > 0 && <span className="agent-companies">{agents.join(" · ")}</span>}
        {company.open_blocking_concerns > 0 && (
          <span className="badge blocking">{company.open_blocking_concerns} blocking</span>
        )}
      </div>
    </Link>
  );
}
