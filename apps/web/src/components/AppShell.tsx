import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { Me } from "../api/types";

const GROUPS: { label: string; links: [string, string][] }[] = [
  {
    label: "Today",
    links: [
      ["/", "Overview"],
      ["/review", "Review"],
    ],
  },
  {
    label: "Pipeline",
    links: [
      ["/companies", "Companies"],
      ["/portfolio", "Portfolio"],
    ],
  },
  {
    label: "Desk",
    links: [
      ["/agents", "Agents"],
      ["/value", "Value"],
    ],
  },
  {
    label: "System",
    links: [["/administration", "Administration"]],
  },
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
          {GROUPS.map((group) => (
            <div key={group.label}>
              <p className="rail-group">{group.label}</p>
              {group.links.map(([path, label]) => (
                <NavLink key={path} to={`${path}${search}`} end={path === "/"}>
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="rail-foot">
          <label htmlFor="principal">Signed in</label>
          <select id="principal" value={me.principal.id} onChange={(event) => onSwitch(event.target.value)}>
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
          value={sectionPath(location.pathname)}
          onChange={(event) => navigate(`${event.target.value}${search}`)}
        >
          {GROUPS.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.links.map(([path, label]) => (
                <option key={path} value={path}>
                  {label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
      <main className="main">
        <div className="fixture-banner">
          {me.mode === "demo"
            ? "Public demo · fictional companies · shared review copy"
            : "Fixture workspace · fictional companies · no live capital"}
        </div>
        <Outlet />
      </main>
    </div>
  );
}

function sectionPath(pathname: string) {
  if (pathname.startsWith("/companies")) return "/companies";
  if (pathname.startsWith("/agents")) return "/agents";
  if (pathname.startsWith("/review")) return "/review";
  if (pathname.startsWith("/portfolio")) return "/portfolio";
  if (pathname.startsWith("/value")) return "/value";
  if (pathname.startsWith("/administration")) return "/administration";
  return "/";
}
