import { useState } from "react";
import { Link } from "react-router-dom";
import { useCompanies } from "../api/queries";
import { STAGES, stageLabel, type CompanyCard } from "../api/types";

export function CompanyFlow({ principalId }: { principalId: string }) {
  const query = useCompanies(principalId);
  const [archive, setArchive] = useState(false);
  const [text, setText] = useState("");
  if (query.isLoading) return <div className="skeleton" />;
  const items = (query.data?.items ?? []).filter((company) => {
    const archived = company.stage === "passed" || company.stage === "paused";
    if (archive !== archived) return false;
    return company.display_name.toLowerCase().includes(text.toLowerCase());
  });
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Companies</h1>
          <p>Stages move through recorded human actions. Cards are not dragged past a gate.</p>
        </div>
        <div className="row-actions">
          <input type="text" placeholder="Search" value={text} onChange={(event) => setText(event.target.value)} aria-label="Search companies" />
          <button className="button secondary" type="button" onClick={() => setArchive((value) => !value)}>
            {archive ? "Show active" : "Show passed and paused"}
          </button>
        </div>
      </header>
      {items.length === 0 && <p className="empty">No companies match this view.</p>}
      {!archive && (
        <div className="columns">
          {STAGES.map((stage) => (
            <section className="column" key={stage}>
              <h2>{stageLabel(stage)}</h2>
              {items
                .filter((company) => company.stage === stage)
                .map((company) => (
                  <CompanyTile key={company.id} company={company} />
                ))}
            </section>
          ))}
        </div>
      )}
      {archive &&
        items.map((company) => (
          <CompanyTile key={company.id} company={company} />
        ))}
    </>
  );
}

function CompanyTile({ company }: { company: CompanyCard }) {
  return (
    <Link className="card company-card" to={`/companies/${company.id}`}>
      <strong>{company.display_name}</strong>
      <div className="meta">{company.owner_name}</div>
      {company.open_blocking_concerns > 0 && (
        <div className="badge blocking">{company.open_blocking_concerns} blocking</div>
      )}
    </Link>
  );
}
