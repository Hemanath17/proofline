/** Hand-written to match the exact dict shapes `Case.to_dict()` and the
 * `/api/cases` routes return (proofline/db/models.py, proofline/routes/
 * cases.py). openapi-typescript can't infer a precise shape from a route
 * typed `-> dict` with no declared Pydantic response_model -- same
 * limitation every existing route in this codebase already has (e.g.
 * review_notes.py), so these stay hand-written rather than generated
 * until those routes grow real response models. */

export type TaxEffect = {
  federal: string;
  california: string;
  kind: string;
  direction: string;
} | null;

export type CaseRow = {
  case_id: string;
  root_cause_key: string;
  origin: string;
  origin_ref: string | null;
  scope: string;
  claims: string[];
  severity: string;
  finding_type: string | null;
  priority: number;
  assignee_id: string | null;
  status: string;
  revision: number;
  check_id: string | null;
  check_version: number | null;
  evidence_refs: string[];
  observed: string | null;
  expected: string | null;
  limitations: string | null;
  recommended_action: string | null;
  tax_effect: TaxEffect;
  impact_unknown: boolean;
  cleared_reason: string | null;
  created_at: string;
  updated_at: string;
  changed_since_last_seen: boolean;
  change_summary: string | null;
  why_it_here: string | null;
  title: string | null;
  proposal_count: number;
};

export type CaseProposal = {
  id: string;
  case_id: string;
  revision_number: number;
  resolution_type: string;
  fields: Record<string, unknown>;
  evidence_refs: string[];
  proposed_by: string;
  proposed_at: string;
};

export type CaseDecision = {
  id: string;
  case_id: string;
  proposal_revision: number | null;
  decision: string;
  decided_by: string;
  decided_at: string;
  note: string | null;
};

export type CaseDetail = CaseRow & {
  proposals: CaseProposal[];
  decisions: CaseDecision[];
};

export type QueueGroup = {
  severity: string;
  count: number;
  total_tax_effect: { federal: string; california: string };
  cases: CaseRow[];
};

export type QueueResponse = {
  tab: string;
  counts: Record<string, number>;
  groups: QueueGroup[];
};

export type Highlight = {
  ev_id: string;
  field: string;
  label: string | null;
  tag: number;
  position: { x0: number; y0: number; x1: number; y1: number } | null;
};

export type TraceSourcePage = {
  page: number;
  highlights: Highlight[];
};

export type TraceSource = {
  document_id: string;
  title: string;
  pages: TraceSourcePage[];
};

export type OtherSource = { ref: string; kind: string };

export type ExcludedDocument = { document_id: string; reason: string };

export type Adjustment = {
  id: string;
  claim_key: string;
  old_value: string;
  new_value: string;
  evidence_refs: string[];
  case_id: string | null;
  decision_id: string | null;
  created_at: string;
};

export type LineTraceResponse = {
  line_key: string;
  version: string;
  value: unknown;
  /** "engine v3" | "exact" | "adjusted" (docs/UX.md Label vocabulary). */
  provenance: string;
  /** The line's own human-readable label (e.g. "Short-term from Form
   * 8949 box B") -- distinct from `provenance`. */
  label: string;
  rule: string;
  inputs: string[];
  used_by: string[];
  primary_sources: string[];
  sources: TraceSource[];
  other_sources: OtherSource[];
  excluded: ExcludedDocument[];
  note: string | null;
  adjustment: Adjustment | null;
};

export type DocumentDetail = {
  id: string;
  title: string;
  document_type: string;
  issuer: string | null;
  tax_year: number | null;
  received_at: string | null;
  page_count: number;
  marked_corrected: boolean | null;
  pages: number[];
  extraction_status: string;
  disposition: string | null;
  disposition_reason: string | null;
  disposition_confirmed_by: string | null;
  disposition_revision: number;
  proposed_disposition: string;
  proposed_reason: string | null;
  extraction_complete: boolean;
  lines_using: string[];
  used: boolean;
  note: string | null;
};

export type SignOff = {
  id: string;
  scope: string;
  version: number;
  signed_by: string;
  signed_role: string;
  signed_at: string;
  engine_version: string;
  active_adjustment_ids: string[];
  check_run_id: string | null;
  evidence_fingerprint: string;
  values_fingerprint: string;
  decisions_fingerprint: string;
  scope_fingerprint: string;
};

export type TieOut = {
  line_key: string;
  label: string | null;
  engine_value: unknown;
  workpaper_value: unknown;
  ok: boolean;
  difference: string;
};

export type AreaDetailRow = {
  line_key: string;
  label: string | null;
  claim_key: string | null;
  value: unknown;
  provenance_label: string;
  verified: boolean;
  verified_by: string | null;
};

export type ChangedClaim = {
  claim_key: string;
  old_value: unknown;
  new_value: unknown;
};

export type ReplacedDocument = {
  old_document_id: string;
  new_document_id: string;
  confirmed: boolean;
  unchanged_count: number;
  changed_count: number;
  changed: ChangedClaim[];
};

export type ChangesSinceSignOff = {
  since_version: number;
  value_changed: boolean;
  evidence_only_changed: boolean;
  scope_changed: boolean;
  decision_changed: boolean;
  documents: ReplacedDocument[];
} | null;

export type AreaDetail = {
  scope: string;
  sign_off: SignOff | null;
  active_adjustments_count: number;
  blocking_reasons: string[];
  changes_since_sign_off: ChangesSinceSignOff;
  tie_outs: TieOut[];
  detail: AreaDetailRow[];
};

export type DocumentPage = {
  document_id: string;
  page: number;
  printed_content: string;
};

export type ActivityEvent = {
  event_type: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  occurred_at: string | null;
  revision: number | null;
  payload: Record<string, unknown>;
};
