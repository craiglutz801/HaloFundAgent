import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import type { Me } from "../api/types";
import { PHASES, phaseLabel } from "../api/types";

const AGENTS = [
  ["ainge", "Ainge"],
  ["xavier", "Xavier"],
  ["mutombo", "Mutombo"],
  ["scout", "Scout"],
  ["stockton", "Stockton"],
  ["sloan", "Sloan"],
  ["trainer", "Trainer"],
  ["scorekeeper", "Scorekeeper"],
  ["gm", "GM"],
];

const LINKS = [
  ["/", "Overview"],
  ["/companies", "Companies"],
  ["/agents", "Agents"],
  ["/review", "Review"],
  ["/portfolio", "Portfolio"],
  ["/value", "Value"],
  ["/administration", "Administration"],
];

export function AppShell({
  me,
  roster,
  onSwitch,
}: {
  me: Me;
  roster: { id: string; display_name: string; role: string }[];
  onSwitch: (principalId: string) => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const search = location.search;
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <div>
            <strong>HALO</strong>
            <span>Front Office</span>
          </div>
          <img className="brand-mark" src="/halo-mark.jpg" alt="" width="44" height="44" />
        </div>
        <nav>
          {LINKS.map(([path, label]) => (
            <NavLink key={path} to={`${path}${search}`} end={path === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <label htmlFor="principal">Signed in</label>
          <select
            id="principal"
            value={me.principal.id}
            onChange={(event) => onSwitch(event.target.value)}
          >
            {roster.map((person) => (
              <option key={person.id} value={person.id}>
                {person.display_name}
              </option>
            ))}
          </select>
        </div>
      </aside>
      <div className="mobile-nav">
        <div className="mobile-brand">
          <span>Halo Front Office</span>
          <img className="brand-mark" src="/halo-mark.jpg" alt="" width="36" height="36" />
        </div>
        <select
          aria-label="Section"
          value={location.pathname}
          onChange={(event) => navigate(`${event.target.value}${search}`)}
        >
          {LINKS.map(([path, label]) => (
            <option key={path} value={path}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <main className="main">
        <div className="fixture-banner">
          {me.mode === "demo"
            ? "Public demo · fictional companies · shared review copy"
            : "Fixture workspace · fictional companies · no live capital"}
        </div>
        <FilterBar />
        <Outlet />
      </main>
    </div>
  );
}

function FilterBar() {
  const [params, setParams] = useSearchParams();
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };
  const applied = ["q", "agent", "phase", "scope", "outcome"].some((key) => params.get(key));
  return (
    <div className="filter-bar">
      <input
        type="text"
        placeholder="Search companies or projects"
        aria-label="Search companies or projects"
        value={params.get("q") ?? ""}
        onChange={(event) => set("q", event.target.value)}
      />
      <select aria-label="Agent" value={params.get("agent") ?? ""} onChange={(event) => set("agent", event.target.value)}>
        <option value="">All agents</option>
        {AGENTS.map(([id, name]) => (
          <option key={id} value={id}>
            {name}
          </option>
        ))}
      </select>
      <select aria-label="Phase" value={params.get("phase") ?? ""} onChange={(event) => set("phase", event.target.value)}>
        <option value="">All phases</option>
        {PHASES.map((phase) => (
          <option key={phase} value={phase}>
            {phaseLabel(phase)}
          </option>
        ))}
      </select>
      <select aria-label="Project scope" value={params.get("scope") ?? ""} onChange={(event) => set("scope", event.target.value)}>
        <option value="">Any project status</option>
        <option value="active">Active projects</option>
        <option value="paused">Paused projects</option>
        <option value="past">Past projects</option>
        <option value="all">All projects</option>
      </select>
      {applied && (
        <button className="button secondary" type="button" onClick={() => setParams(new URLSearchParams())}>
          Clear all
        </button>
      )}
    </div>
  );
}
