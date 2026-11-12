import { useSearchParams } from "react-router-dom";
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

export function FilterBar() {
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
