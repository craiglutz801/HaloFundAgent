# Data dictionary

Every business row is scoped by `organization_id` and `workspace_id` unless it is the organization itself or a session. Identifiers are UUIDs. Timestamps are `timestamptz` in UTC. Money and rates use `numeric`, not binary floats. A metric observation may store a null value only when completeness is `missing` or `invalid`.

The application role can read through row-security policies. It can insert reviews, decisions, dispositions, stage events, audit rows, outbox rows, notifications, and idempotency keys. It can update companies, cases, concerns, packets, and notification acknowledgement fields. It cannot update or delete decisions, reviews, or dispositions.

| Table | Purpose |
|---|---|
| `organizations` | Tenant, policy version, and `fixture` or `live` mode |
| `principals` | Human or service identity |
| `organization_memberships` | Role inside an organization |
| `workspaces` | Fund aggregate or one company |
| `workspace_memberships` | Explicit capabilities on a workspace |
| `companies` | Canonical company. `stage` is a guarded projection |
| `investment_cases` | Initial, follow-on, or exit case |
| `stage_events` | The only legal source of a stage change |
| `documents` | Immutable document versions and content hashes |
| `evidence_records` | Locator, excerpt, period, and limitations |
| `evidence_snapshots` | Frozen evidence set for a case |
| `snapshot_evidence` | Membership of a snapshot |
| `fund_bundle_items` | Authorized cross-workspace projection. Not a raw copy of private text |
| `agent_runs` | One durable run. Status is not a boolean complete flag |
| `run_grants` | Narrow permission for a run and phase |
| `artifacts` | Versioned specialist output and hash |
| `artifact_dependencies` | Lineage used to mark stale downstream work |
| `artifact_source_scopes` | Visibility requirements inherited by a derived artifact |
| `findings` | Statement, kind, and confidence |
| `finding_evidence` | Support, contradict, or context |
| `concerns` | Blocking and non-blocking questions |
| `concern_dispositions` | Append-only resolution. A waiver is not accepted by the API |
| `reviews` | Human review bound to an artifact hash |
| `ic_packets` | Frozen manifest for a decision |
| `decisions` | Append-only approve, pass, defer, or terms revision |
| `close_records` | Verified closing document. Agents cannot insert one |
| `metric_definitions` | Unit, cadence, and freshness limit |
| `metric_observations` | Period value, completeness, and evidence |
| `initiatives` | Human-owned Stockton or Sloan work |
| `value_entries` | Observed, estimated, verified, or unverified amounts |
| `playbooks` | Draft or published operating play |
| `report_releases` | Audience-bound release. Not enabled for external send |
| `budget_reservations` | Spend reservation for a future provider call |
| `provider_calls` | Record of a model call. Fixture mode does not insert successful generations |
| `audit_events` | Append-only audit |
| `outbox_events` | Pending integration events. No dispatcher consumes them yet |
| `activity_outcomes` | Idempotency record reserved for workflow activities |
| `idempotency_keys` | Request hash and stored response |
| `notifications` | Visible only to the recipient principal |
| `sessions` | Token hash only. The raw session token is not stored |

Fixture primary keys are UUID v5 values from the namespace `8c1c6b2e-7a4d-4f0a-9b1e-2d5a6c7e8f90`, so a reset reloads the same identifiers.
