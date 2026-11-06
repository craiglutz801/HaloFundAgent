import { phaseLabel } from "../api/types";

export function CompanyHeader({
  name,
  legalName,
  phase,
  outcome,
  owner,
  otherOpen,
}: {
  name: string;
  legalName: string;
  phase: string;
  outcome: string;
  owner: string;
  otherOpen?: string;
}) {
  const label = outcome === "portfolio" ? "Portfolio" : outcome === "passed" ? "Passed" : phaseLabel(phase);
  return (
    <header className="page-head">
      <div>
        <p className="kicker">{legalName}</p>
        <h1>{name}</h1>
        <p>Owner {owner}</p>
        {otherOpen && <p className="meta">{otherOpen}</p>}
      </div>
      <span className="badge">{label}</span>
    </header>
  );
}
