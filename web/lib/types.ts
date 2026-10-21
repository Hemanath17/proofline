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

/** `GET /api/trace/evidence?ref=`'s response (proofline/routes/trace.py
 * `_evidence_preview_dict`) -- a clickable preview for any evidence
 * reference format docs/PACKET.md names, shown in the Trace drawer. */
export type EvidencePreview =
  | {
      kind: "document_field";
      ref: string;
      document_id: string;
      document_title: string;
      page: number;
      field: string;
      label: string | null;
      value: unknown;
      text_as_read: string | null;
      position: Highlight["position"];
    }
  | {
      kind: "document";
      ref: string;
      document_id: string;
      title: string;
      document_type: string;
      issuer: string | null;
    }
  | {
      kind: "document_page";
      ref: string;
      document_id: string | null;
      document_title: string | null;
      page: number;
    }
  | {
      kind: "questionnaire_item";
      ref: string;
      question: string;
      answer: unknown;
      answered_by: string | null;
      answered_at: string | null;
    }
  | { kind: "message"; ref: string; from: string; to: string; sent_at: string; text: string }
  | { kind: "call_note"; ref: string; date: string; participants: string[]; notes: string[] }
  | { kind: "typed"; ref: string; label: string; value: unknown };

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

/** Step 9 (B14/B26): the notifications feed. */
export type NotificationCase = {
  entity_type: "case";
  entity_id: string;
  label: string;
  scope?: string;
  status?: string;
  changed_at?: string;
};

export type NotificationDeadline = {
  label: string;
  date: string;
  days_remaining: number;
  overdue: boolean;
};

export type NotificationsResponse = {
  needs_me: NotificationCase[];
  changed: NotificationCase[];
  deadlines: NotificationDeadline[];
};

/** Step 9 (B37): time against budget. */
export type AreaTimeBudget = {
  area: string;
  budget_hours: string | null;
  logged_hours: string;
  over_budget: boolean;
};

export type TimeEntry = {
  event_id: string;
  actor_id: string | null;
  area: string;
  hours: string;
  date: string;
  note: string | null;
};

export type TimeReport = {
  budget: AreaTimeBudget[];
  entries: TimeEntry[];
};

/** Step 9 (B38): search. */
export type SearchResult = {
  type: "case" | "line" | "document" | "note";
  id: string;
  title: string;
  snippet: string;
};

/** Step 9 (B15): comparing versions. */
export type VersionDiffLine = {
  line_key: string;
  label: string | null;
  rule: string | null;
  old_value: unknown;
  new_value: unknown;
  changed: boolean;
  source: string;
};

export type VersionDiffResponse = {
  from: string;
  to: string;
  lines: VersionDiffLine[];
};

/** Step 9 (B16): what-ifs. */
export type WhatIfChangedLine = {
  line_key: string;
  change: string;
  what_if_old: unknown;
  what_if_new: unknown;
  current_workpaper_value: unknown;
};

export type WhatIfAlternative = {
  id: string;
  description: string | null;
  base_version: string;
  choices: Record<string, unknown>;
  federal: Record<string, unknown>;
  california: Record<string, unknown>;
  changed_lines: WhatIfChangedLine[];
};

export type WhatIfsResponse = {
  alternatives: WhatIfAlternative[];
};

/** Step 9 (B19): judgments and elections. */
export type Judgment = {
  id: string;
  recorded_by: string | null;
  authority: string;
  approved_by: string;
  reasoning: string;
  claim_key: string | null;
  is_election: boolean;
  what_if_id: string | null;
  case_id: string | null;
  occurred_at: string | null;
};

export type DueDiligenceChecklist = {
  checklist: Array<{ item: string; description: string; line_key?: string }>;
  done: boolean;
  confirmed_by: string | null;
  confirmed_at: string | null;
  note: string | null;
};

/** Step 9 (B20): outside filings. */
export type OutsideFilingItem = {
  item: string;
  label: string;
  evidence_refs: string[];
  note: string;
  decided: boolean;
  decision: string | null;
  decided_by: string | null;
  decided_note: string | null;
};

/** Step 9 (S5): the client workspace. */
export type ClientSummary = {
  federal: { balance_due: unknown; label: string };
  california: { balance_due: unknown; label: string };
};

export type ClientQuestionThread = {
  case_id: string;
  question: string;
  asked_at: string | null;
  answer: string | null;
  answered_at: string | null;
};

export type ClientDocument = {
  id: string;
  title: string;
  document_type: string;
  issuer: string | null;
  received_at: string | null;
  kind: "uploaded" | "filed";
};

export type ClientPackageSummary = {
  reference: string;
  amounts_fingerprint: string;
  identity_fingerprint: string;
  engine_version: string;
  summary: ClientSummary;
};
