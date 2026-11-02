import { NavLink, Outlet, useNavigate } from "react-router-dom";
import type { Me } from "../api/types";

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
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <strong>HALO</strong>
          <span>Front Office</span>
        </div>
        <nav>
          {LINKS.map(([path, label]) => (
            <NavLink key={path} to={path} end={path === "/"}>
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
        <select
          aria-label="Section"
          defaultValue={window.location.pathname}
          onChange={(event) => navigate(event.target.value)}
        >
          {LINKS.map(([path, label]) => (
            <option key={path} value={path}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <main className="main">
        <div className="fixture-banner">Fixture workspace · fictional companies · no live capital</div>
        <Outlet />
      </main>
    </div>
  );
}
