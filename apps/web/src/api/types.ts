export type Me = {
  principal: { id: string; display_name: string; email: string };
  mode: string;
  policy_version: string;
  workspaces: {
    id: string;
    name: string;
    kind: string;
    company_id: string | null;
    role: string;
    capabilities: string[];
  }[];
};

export type DecisionCard = {
  packet_id: string;
  case_id: string;
  company_id: string;
  company_name: string;
  case_type: string;
  owner_name: string;
  due_at: string | null;
  reason: string;
  manifest_sha256: string;
};

export type Overview = {
  decisions: DecisionCard[];
  blockers: {
    concern_id: string;
    case_id: string;
    company_id: string;
    company_name: string;
    question: string;
    severity: string;
    owner_name: string;
  }[];
  portfolio_attention: { company_id: string; company_name: string; health: string; reason: string }[];
  stage_counts: { stage: string; count: number }[];
  notifications: { id: string; title: string; body: string; severity: string; created_at: string }[];
  synced_at: string;
};

export type CompanyCard = {
  id: string;
  process_id?: string;
  display_name: string;
  legal_name: string;
  website: string;
  stage: string;
  phase?: string;
  phase_label?: string;
  outcome?: string;
  on_hold?: boolean;
  case_type?: string;
  owner_name: string;
  open_blocking_concerns: number;
  row_version: number;
  active_agents?: string[];
};

export type AssignmentCard = {
  id: string;
  agent_id: string;
  agent_name: string;
  title: string;
  objective: string;
  status: string;
  working_now: boolean;
  working_state: string | null;
  process_id: string | null;
  phase: string | null;
  phase_label: string | null;
  last_activity_at: string | null;
  run_id: string | null;
  run_status: string | null;
};

export type Evidence = {
  id: string;
  kind: string;
  locator: Record<string, unknown>;
  excerpt: string;
  observed_start: string | null;
  observed_end: string | null;
  collected_at: string | null;
  sample_size: string;
  origin_class: string;
  limitations: string[];
  status: string;
  document: { id: string; filename: string; mime: string; sha256: string; version: number; source_kind: string } | null;
};

export type Artifact = {
  id: string;
  run_id: string;
  kind: string;
  phase: string;
  version: number;
  sha256: string;
  status: string;
  sealed_at: string | null;
  content: Record<string, unknown>;
};

export type CompanyDetail = {
  company: {
    id: string;
    legal_name: string;
    display_name: string;
    website: string;
    stage: string;
    owner_name: string;
    row_version: number;
  };
  cases: {
    id: string;
    case_type: string;
    status: string;
    owner_name: string;
    due_at: string | null;
    row_version: number;
    policy_version: string;
    phase?: string;
    phase_label?: string;
    outcome?: string;
    on_hold?: boolean;
    primary?: boolean;
    ic_gaps: { kind: string; label: string }[];
  }[];
  assignments?: AssignmentCard[];
  applied_filters?: Record<string, unknown>;
  filter_restricted?: boolean;
  stage_events: { id: string; from_stage: string; to_stage: string; reason: string; created_at: string }[];
  concerns: {
    id: string;
    case_id: string;
    question: string;
    severity: string;
    blocking: boolean;
    status: string;
    owner_name: string;
    row_version: number;
    due_at: string | null;
  }[];
  runs: {
    id: string;
    case_id: string | null;
    agent_name: string;
    phase: string;
    status: string;
    status_detail: string;
    provider: string;
    model: string;
  }[];
  artifacts: Artifact[];
  reviews: { id: string; artifact_id: string; artifact_sha256: string; verdict: string; notes: string; reviewed_at: string }[];
  evidence: Evidence[];
  packets: { id: string; case_id: string; version: number; status: string; manifest_sha256: string; policy_version: string }[];
};

export type Packet = {
  id: string;
  status: string;
  version: number;
  manifest_sha256: string;
  policy_version: string;
  case: { id: string; case_type: string; status: string; row_version: number };
  company: { id: string; display_name: string; stage: string };
  can_decide: boolean;
  artifacts: Artifact[];
  concerns: { id: string; question: string; severity: string; blocking: boolean; status: string }[];
  decision: { id: string; decision: string; rationale: string; decided_at: string; packet_sha256: string } | null;
};

export const PHASES = [
  "sourcing",
  "screening",
  "partner_review",
  "due_diligence",
  "investment_committee",
  "term_sheet",
  "negotiation_closing",
] as const;

export const PHASE_SHORT: Record<string, string> = {
  sourcing: "Source",
  screening: "Screen",
  partner_review: "Partner",
  due_diligence: "Diligence",
  investment_committee: "Committee",
  term_sheet: "Terms",
  negotiation_closing: "Close",
};

export const PHASE_LABELS: Record<string, string> = {
  sourcing: "Sourcing",
  screening: "Screening",
  partner_review: "Deep dive / Partner review",
  due_diligence: "Due diligence",
  investment_committee: "Investment Committee",
  term_sheet: "Term sheet",
  negotiation_closing: "Negotiation / Closing",
  unknown: "Phase unknown",
};

export const STAGES = [
  "discovered",
  "first_look",
  "diligence",
  "ic_review",
  "closing",
  "owned",
  "exited",
] as const;

export function stageLabel(stage: string) {
  return PHASE_LABELS[stage] ?? stage.replaceAll("_", " ");
}

export function phaseLabel(phase: string) {
  return PHASE_LABELS[phase] ?? phase.replaceAll("_", " ");
}

export function formatWhen(value: string | null | undefined) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";
  // dateStyle cannot be combined with timeZoneName in every Intl build.
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

export function hasCapability(me: Me | undefined, capability: string) {
  return Boolean(me?.workspaces.some((workspace) => workspace.capabilities.includes(capability)));
}
