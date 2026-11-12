import type { ReactNode } from "react";
import { phaseLabel } from "../api/types";

export function CompanyHeader({
  name,
  legalName,
  phase,
  outcome,
  owner,
  otherOpen,
  actions,
}: {
  name: string;
  legalName: string;
  phase: string;
  outcome: string;
  owner: string;
  otherOpen?: string;
  actions?: ReactNode;
}) {
  const label = outcome === "portfolio" ? "Portfolio" : outcome === "passed" ? "Passed" : phaseLabel(phase);
  return (
    <header className="page-head">
      <div>
        <p className="kicker">{legalName}</p>
        <h1>{name}</h1>
        <p>
          Owner {owner}
          {otherOpen ? ` · ${otherOpen}` : ""}
        </p>
      </div>
      <div className="page-head-side">
        <span className="badge">{label}</span>
        {actions}
      </div>
    </header>
  );
}
