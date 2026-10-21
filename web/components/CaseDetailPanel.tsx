"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import { useCurrentActor } from "@/lib/session";
import { useCaseDetail } from "@/lib/useCaseDetail";
import { availableActions, type CaseAction } from "@/lib/caseActions";
import { CaseStatusPill, severityLabel, TaxEffectDisplay } from "@/components/Badges";
import { openEvidencePreview } from "@/lib/traceDrawer";
import type { ActivityEvent, CaseProposal } from "@/lib/types";
import styles from "./CaseDetailPanel.module.css";

/** What happens next from each C1 status (docs/CONTRACTS.md C1) --
 * replaces a linear stepper, which would misrepresent a state machine
 * that moves backward (`return`, `partner_return`, `reopen`) and
 * sideways (`ask_client`/`client_answered`), and that can exit without
 * ever reaching `resolved` (`clear`). See docs/DECISIONS.md. */
const STATUS_NEXT_ACTION: Record<string, string> = {
  open: "Next: a preparer picks this up to start investigating.",
  investigating: "Next: the preparer asks the client, or submits a proposal for review.",
  waiting_on_client:
    "Waiting on the client's answer. Recording it returns this case to investigating.",
  in_review:
    "Next: a reviewer approves (to Resolved, or Awaiting partner if the tax effect is over 1,000) or returns it to investigating.",
  awaiting_partner: "Next: the partner approves (to Resolved) or returns it to investigating.",
  resolved: "Resolved. A reviewer or the system can reopen it if something changes.",
  cleared: "Cleared -- the finding stopped firing.",
};

const CLIENT_EVIDENCE_PREFIXES = ["qa-", "msg-", "call-"];

function isClientEvidence(ref: string): boolean {
  return CLIENT_EVIDENCE_PREFIXES.some((prefix) => ref.startsWith(prefix));
}

const RESOLUTION_FIELDS: Record<string, Array<{ key: string; label: string }>> = {
  resolve_evidence_conflict: [
    { key: "evidence_a", label: "Evidence A (ref)" },
    { key: "evidence_b", label: "Evidence B (ref)" },
    { key: "chosen", label: "Chosen (a or b)" },
    { key: "reason", label: "Reason" },
  ],
  record_judgment: [
    { key: "reasoning", label: "Reasoning" },
    { key: "authority", label: "Authority relied on" },
    { key: "approved_by", label: "Approved by (CPA staff id)" },
  ],
  adjust_number: [
    { key: "claim", label: "Claim" },
    { key: "old_value", label: "Old value" },
    { key: "new_value", label: "New value" },
  ],
  mark_legitimate: [{ key: "reason", label: "Reason the difference is expected" }],
};

const ACTION_FIELD: Record<CaseAction, { key: string; label: string; required: boolean } | null> = {
  pick_up: null,
  ask_client: { key: "question", label: "Question for the client", required: true },
  client_answered: { key: "evidence_ref", label: "Evidence ref (e.g. msg-10)", required: true },
  submit_proposal: null,
  return: { key: "note", label: "Note (why it's being returned)", required: true },
  approve: { key: "note", label: "Note (optional)", required: false },
  partner_approve: { key: "note", label: "Note (optional)", required: false },
  partner_return: { key: "note", label: "Note (why it's being returned)", required: true },
  reopen: { key: "reason", label: "Reason", required: true },
  reassign: { key: "assignee_id", label: "New assignee (staff id)", required: true },
};

const ACTION_ENDPOINT: Record<CaseAction, string> = {
  pick_up: "pick-up",
  ask_client: "ask-client",
  client_answered: "client-answered",
  submit_proposal: "submit-proposal",
  return: "return",
  approve: "approve",
  partner_approve: "partner-approve",
  partner_return: "partner-return",
  reopen: "reopen",
  reassign: "reassign",
};

function ProposalForm({
  caseId,
  revision,
  availableEvidence,
  onDone,
}: {
  caseId: string;
  revision: number;
  availableEvidence: string[];
  onDone: () => void;
}) {
  const [resolutionType, setResolutionType] = useState("mark_legitimate");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [selectedEvidence, setSelectedEvidence] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requiredFields = RESOLUTION_FIELDS[resolutionType] ?? [];
  const missing = requiredFields.some((field) => !fields[field.key]?.trim());
  const evidenceRefs = availableEvidence.filter((ref) => selectedEvidence[ref]);
  const needsEvidence = resolutionType !== "record_judgment" && evidenceRefs.length === 0;
  const disabled = missing || needsEvidence;
  const disabledReason = missing
    ? "fill in every field for this resolution type"
    : needsEvidence
      ? "needs at least one piece of supporting evidence"
      : undefined;

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await apiPost(`/api/cases/${caseId}/submit-proposal`, {
        expected_revision: revision,
        resolution_type: resolutionType,
        fields,
        evidence_refs: evidenceRefs,
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to submit");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.proposalForm}>
      <label className={styles.field}>
        <span>Resolution type</span>
        <select
          value={resolutionType}
          onChange={(event) => {
            setResolutionType(event.target.value);
            setFields({});
          }}
        >
          <option value="resolve_evidence_conflict">Resolve evidence conflict</option>
          <option value="record_judgment">Record judgment</option>
          <option value="adjust_number">Adjust a number</option>
          <option value="mark_legitimate">Mark legitimate</option>
        </select>
      </label>
      {requiredFields.map((field) => (
        <label key={field.key} className={styles.field}>
          <span>{field.label}</span>
          <input
            value={fields[field.key] ?? ""}
            onChange={(event) => setFields((prev) => ({ ...prev, [field.key]: event.target.value }))}
          />
        </label>
      ))}
      <fieldset className={styles.evidencePicker}>
        <legend>Evidence (from this case)</legend>
        {availableEvidence.length === 0 && (
          <p className={styles.small}>No evidence attached to this case yet.</p>
        )}
        {availableEvidence.map((ref) => (
          <div key={ref} className={styles.evidenceOption}>
            <label className={styles.evidenceOptionLabel}>
              <input
                type="checkbox"
                checked={Boolean(selectedEvidence[ref])}
                onChange={(event) =>
                  setSelectedEvidence((prev) => ({ ...prev, [ref]: event.target.checked }))
                }
              />
              <span className="mono">{ref}</span>
            </label>
            <button
              type="button"
              className={styles.previewLink}
              onClick={() => openEvidencePreview(ref)}
            >
              Preview
            </button>
          </div>
        ))}
      </fieldset>
      {error && <p className={styles.error}>{error}</p>}
      <button
        type="button"
        className={styles.primaryButton}
        disabled={disabled || submitting}
        title={disabledReason}
        onClick={submit}
      >
        {submitting ? "Submitting..." : "Submit proposal"}
      </button>
      {disabledReason && <p className={styles.disabledReason}>{disabledReason}</p>}
    </div>
  );
}

function DecisionButton({
  caseId,
  revision,
  action,
  label,
  nextStatusHint,
  onDone,
}: {
  caseId: string;
  revision: number;
  action: CaseAction;
  label: string;
  nextStatusHint?: string;
  onDone: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = ACTION_FIELD[action];

  async function run() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { expected_revision: revision };
      if (field) payload[field.key] = value;
      await apiPost(`/api/cases/${caseId}/${ACTION_ENDPOINT[action]}`, payload);
      setConfirming(false);
      setValue("");
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!confirming) {
    return (
      <button
        type="button"
        className={styles.decisionButton}
        onClick={() => setConfirming(true)}
      >
        {label}
        {nextStatusHint && <span className={styles.nextHint}> {nextStatusHint}</span>}
      </button>
    );
  }

  return (
    <div className={styles.confirmBox}>
      {field && (
        <label className={styles.field}>
          <span>{field.label}</span>
          <input value={value} onChange={(event) => setValue(event.target.value)} autoFocus />
        </label>
      )}
      {error && <p className={styles.error}>{error}</p>}
      <div className={styles.confirmActions}>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={submitting || (field?.required && !value.trim())}
          onClick={run}
        >
          {submitting ? "Working..." : `Confirm ${label.toLowerCase()}`}
        </button>
        <button type="button" className={styles.secondaryButton} onClick={() => setConfirming(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function ActivityFeed({ caseId }: { caseId: string }) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ events: ActivityEvent[] }>(`/api/cases/${caseId}/activity`)
      .then((body) => {
        if (!cancelled) setEvents(body.events);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  return (
    <ul className={styles.activityList}>
      {events.map((event, index) => (
        <li key={index} className={styles.activityRow}>
          <span className={styles.activityType}>{event.event_type.replaceAll("_", " ")}</span>
          <span className={styles.activityMeta}>
            {event.actor_name} ({event.actor_role}) ·{" "}
            {event.occurred_at ? new Date(event.occurred_at).toLocaleString() : ""}
            {event.revision != null ? ` · revision ${event.revision}` : ""}
          </span>
        </li>
      ))}
      {events.length === 0 && <li className={styles.activityEmpty}>No activity yet.</li>}
    </ul>
  );
}

export function CaseDetailPanel({ caseId }: { caseId: string }) {
  const { actor } = useCurrentActor();
  const { caseDetail, loading, error, refetch } = useCaseDetail(caseId);

  if (loading && !caseDetail) return <p className={styles.loading}>Loading the case...</p>;
  if (error) {
    return (
      <div className={styles.errorState}>
        <p className={styles.error}>{error}</p>
        <button type="button" className={styles.retryButton} onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }
  if (!caseDetail) return null;

  const nextAction = STATUS_NEXT_ACTION[caseDetail.status];
  const actions = availableActions(actor, caseDetail);
  const decisionActions = actions.filter((a) => a.action !== "submit_proposal");
  const canSubmitProposal = actions.some((a) => a.action === "submit_proposal" && a.enabled);

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>{caseDetail.title ?? caseDetail.case_id}</h2>
        <div className={styles.metaRow}>
          <CaseStatusPill status={caseDetail.status} />
          <span className={styles.metaItem}>{severityLabel(caseDetail.severity)}</span>
          <span className={styles.metaItem}>{caseDetail.scope}</span>
          {caseDetail.tax_effect && (
            <TaxEffectDisplay
              federal={caseDetail.tax_effect.federal}
              california={caseDetail.tax_effect.california}
              kind={caseDetail.tax_effect.kind}
              direction={caseDetail.tax_effect.direction}
            />
          )}
          {caseDetail.assignee_id && <span className={styles.metaItem}>Assigned: {caseDetail.assignee_id}</span>}
        </div>
        {nextAction && <p className={styles.nextAction}>{nextAction}</p>}
        {caseDetail.changed_since_last_seen && caseDetail.change_summary && (
          <p className={styles.changeBanner}>Changed since you last looked: {caseDetail.change_summary}</p>
        )}
      </header>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Why this is flagged</h3>
        <p>{caseDetail.observed}</p>
        <p>{caseDetail.expected}</p>
        {caseDetail.limitations && <p className={styles.small}>{caseDetail.limitations}</p>}
        {caseDetail.check_id && (
          <p className={`mono ${styles.small}`}>
            {caseDetail.check_id} v{caseDetail.check_version}
          </p>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Evidence</h3>
        <ul className={styles.evidenceList}>
          {caseDetail.evidence_refs.map((ref) => (
            <li key={ref}>
              <button
                type="button"
                className={styles.evidenceCard}
                onClick={() => openEvidencePreview(ref)}
              >
                <span className="mono">{ref}</span>
                {isClientEvidence(ref) && (
                  <span className={styles.clientNote}>Client said · client statement, not verification</span>
                )}
              </button>
            </li>
          ))}
          {caseDetail.evidence_refs.length === 0 && <li className={styles.small}>No evidence yet.</li>}
        </ul>
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Proposal</h3>
        {caseDetail.proposals.length > 0 && (
          <ol className={styles.revisionList}>
            {caseDetail.proposals.map((proposal: CaseProposal) => (
              <li key={proposal.id} className={styles.revisionItem}>
                <strong>Revision {proposal.revision_number}</strong> · {proposal.resolution_type} · by{" "}
                {proposal.proposed_by}
              </li>
            ))}
          </ol>
        )}
        {canSubmitProposal && (
          <ProposalForm
            caseId={caseDetail.case_id}
            revision={caseDetail.revision}
            availableEvidence={caseDetail.evidence_refs}
            onDone={refetch}
          />
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Activity</h3>
        <ActivityFeed caseId={caseDetail.case_id} />
      </section>

      <footer className={styles.decisionBar}>
        {decisionActions.map((action) =>
          action.enabled ? (
            <DecisionButton
              key={action.action}
              caseId={caseDetail.case_id}
              revision={caseDetail.revision}
              action={action.action}
              label={action.label}
              nextStatusHint={action.nextStatusHint}
              onDone={refetch}
            />
          ) : (
            <button
              key={action.action}
              type="button"
              className={styles.decisionButtonDisabled}
              disabled
              title={action.reason}
            >
              {action.label}
              {action.reason && <span className={styles.disabledReasonInline}> ({action.reason})</span>}
            </button>
          ),
        )}
      </footer>
    </div>
  );
}
