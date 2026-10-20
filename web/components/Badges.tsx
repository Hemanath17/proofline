import styles from "./Badges.module.css";

/** Where a number came from (docs/UX.md Label vocabulary). Only the kinds
 * Step 5-6 can actually produce are wired up; the rest render as a plain
 * label rather than guessing a color for a kind no API response carries
 * yet. */
const PROVENANCE_LABEL: Record<string, string> = {
  engine: "Engine",
  exact: "Exact",
  estimate: "Estimate",
  "what-if": "What-if",
  adjusted: "Adjusted",
  ai_proposed: "AI-proposed",
  client_said: "Client said",
  simulated: "Simulated",
};

export function ProvenanceBadge({ kind }: { kind: string }) {
  // The API's C3 provenance string is either a known kind ("exact",
  // "adjusted", "estimate", ...) or "engine v3"/"engine v2" -- the engine
  // version is part of the label (docs/UX.md: "Engine v1/v2/v3"), so it's
  // title-cased as a whole rather than looked up verbatim.
  const label = kind.startsWith("engine")
    ? `Engine ${kind.split(" ")[1] ?? ""}`.trim()
    : PROVENANCE_LABEL[kind] ?? kind;
  return <span className={`${styles.badge} ${styles.provenance}`}>{label}</span>;
}

const STATUS_META: Record<string, { label: string; tone: "info" | "changed" | "verified" | "neutral" }> = {
  open: { label: "Open", tone: "info" },
  investigating: { label: "Investigating", tone: "info" },
  waiting_on_client: { label: "Waiting on client", tone: "changed" },
  in_review: { label: "In review", tone: "info" },
  awaiting_partner: { label: "Awaiting partner", tone: "changed" },
  resolved: { label: "Resolved", tone: "verified" },
  cleared: { label: "Cleared", tone: "neutral" },
};

export function CaseStatusPill({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" };
  return <span className={`${styles.badge} ${styles[meta.tone]}`}>{meta.label}</span>;
}

export function caseStatusLabel(status: string): string {
  return STATUS_META[status]?.label ?? status;
}

const SEVERITY_LABEL: Record<string, string> = {
  blocks_filing: "Blocks filing",
  tax_amount: "Tax amount",
  penalty_risk: "Penalty risk",
  info: "Info",
};

export function severityLabel(severity: string): string {
  return SEVERITY_LABEL[severity] ?? severity;
}

function wholeDollars(value: string): string {
  return Math.abs(Number(value)).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

/** The review-state marker (docs/UX.md Label vocabulary, second axis: "what
 * a human did"). Icon plus word, never color alone (WCAG 2.2 AA). Only
 * "unverified"/"verified" are backed by real per-claim data today --
 * "changed"/"blocking" are implemented for when that data exists, not
 * called anywhere yet. */
const REVIEW_STATE_META: Record<string, { icon: string; label: string; tone: string }> = {
  unverified: { icon: "○", label: "Unverified", tone: "neutral" },
  verified: { icon: "✓", label: "Verified", tone: "verified" },
  changed: { icon: "▲", label: "Changed since review", tone: "changed" },
  blocking: { icon: "⊘", label: "Blocking", tone: "blocking" },
};

export function ReviewStateMarker({
  state,
  verifiedBy,
}: {
  state: "unverified" | "verified" | "changed" | "blocking";
  verifiedBy?: string | null;
}) {
  const meta = REVIEW_STATE_META[state];
  const label = state === "verified" && verifiedBy ? `Verified · ${verifiedBy}` : meta.label;
  return (
    <span className={`${styles.badge} ${styles.reviewMarker} ${styles[meta.tone]}`}>
      <span aria-hidden="true">{meta.icon}</span>
      {label}
    </span>
  );
}

export function TaxEffectDisplay({
  federal,
  california,
  kind,
  direction,
}: {
  federal: string;
  california: string;
  kind: string;
  direction: string;
}) {
  return (
    <span className={styles.taxEffect}>
      <span className={`mono ${styles.amount}`}>
        {direction} {wholeDollars(federal)} federal / {wholeDollars(california)} CA
      </span>
      <ProvenanceBadge kind={kind} />
    </span>
  );
}
