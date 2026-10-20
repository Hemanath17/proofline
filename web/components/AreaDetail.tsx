"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import { useCurrentActor } from "@/lib/session";
import { ProvenanceBadge, ReviewStateMarker } from "@/components/Badges";
import { TraceableNumber } from "@/components/TraceableNumber";
import type { AreaDetail as AreaDetailData, AreaTimeBudget, TimeReport } from "@/lib/types";
import styles from "./Shared.module.css";

const SCOPE_LABEL: Record<string, string> = {
  identity: "Identity and household",
  wages: "Wages and stock compensation",
  investments: "Investments and digital assets",
  business: "Business",
  rentals: "Rentals and sale",
  pass_throughs: "Pass-throughs and basis",
  deductions_credits: "Deductions and credits",
  california: "California",
  tax_computation: "Tax computation",
};

function canSign(scope: string, role: string | undefined): boolean {
  if (!role) return false;
  if (scope === "tax_computation") return role === "partner";
  return role === "reviewer" || role === "partner" || role === "quality_reviewer";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString("en-US");
  return String(value);
}

function SignOffHeader({
  scope,
  data,
  onSignedOff,
}: {
  scope: string;
  data: AreaDetailData;
  onSignedOff: () => void;
}) {
  const { actor } = useCurrentActor();
  const [signing, setSigning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changePending =
    data.changes_since_sign_off !== null &&
    (data.changes_since_sign_off.value_changed ||
      data.changes_since_sign_off.scope_changed ||
      data.changes_since_sign_off.decision_changed ||
      data.changes_since_sign_off.documents.some((d) => !d.confirmed));

  const roleReason = canSign(scope, actor?.role)
    ? null
    : scope === "tax_computation"
      ? "needs partner"
      : "needs a reviewer, partner or quality reviewer";
  const disabledReasons = [...data.blocking_reasons, ...(roleReason ? [roleReason] : [])];

  async function signOff() {
    setSigning(true);
    setError(null);
    try {
      await apiPost(`/api/areas/${scope}/sign-off`, {});
      onSignedOff();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to sign off");
    } finally {
      setSigning(false);
    }
  }

  const stateLabel = data.sign_off
    ? changePending
      ? `Signed v${data.sign_off.version} · change pending`
      : `Signed v${data.sign_off.version} · ${data.sign_off.signed_by} · ${new Date(
          data.sign_off.signed_at,
        ).toLocaleDateString()}`
    : "Not signed";

  return (
    <header className={styles.header}>
      <h1>{SCOPE_LABEL[scope] ?? scope}</h1>
      <div className={styles.metaRow}>
        <span
          className={`${styles.statePill} ${
            !data.sign_off ? styles.stateNeutral : changePending ? styles.stateAmber : styles.stateGreen
          }`}
        >
          {stateLabel}
        </span>
        <span className={styles.metaItem}>Engine {data.sign_off?.engine_version ?? "v3"}</span>
        <span className={styles.metaItem}>{data.active_adjustments_count} active adjustment(s)</span>
      </div>
      <div className={styles.signOffRow}>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={disabledReasons.length > 0 || signing}
          onClick={signOff}
        >
          {signing ? "Signing..." : "Sign off"}
        </button>
        {disabledReasons.length > 0 && (
          <ul className={styles.disabledReasons}>
            {disabledReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
      {error && <p className={styles.error}>{error}</p>}
    </header>
  );
}

function ChangesSection({
  scope,
  data,
  onConfirmed,
}: {
  scope: string;
  data: AreaDetailData;
  onConfirmed: () => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const changes = data.changes_since_sign_off;
  if (!changes) return null;

  async function confirm(oldDocumentId: string, newDocumentId: string) {
    setConfirming(oldDocumentId);
    setError(null);
    try {
      await apiPost(`/api/areas/${scope}/confirm-carryover`, {
        old_document_id: oldDocumentId,
        new_document_id: newDocumentId,
      });
      onConfirmed();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to confirm");
    } finally {
      setConfirming(null);
    }
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Changes since sign-off v{changes.since_version}</h2>
      {!changes.value_changed &&
        !changes.scope_changed &&
        !changes.decision_changed &&
        changes.documents.length === 0 && (
          <p className={styles.small}>Nothing has changed in this scope.</p>
        )}
      {changes.value_changed && (
        <p className={styles.changedNote}>A value in this scope changed since the last sign-off.</p>
      )}
      {changes.scope_changed && (
        <p className={styles.changedNote}>New claims entered this scope since the last sign-off.</p>
      )}
      {changes.decision_changed && (
        <p className={styles.changedNote}>A decision in this scope changed since the last sign-off.</p>
      )}
      {changes.documents.map((doc) => (
        <div key={doc.old_document_id} className={styles.replacedDocument}>
          <p>
            <span className="mono">{doc.old_document_id}</span> replaced by{" "}
            <span className="mono">{doc.new_document_id}</span> · {doc.unchanged_count} unchanged,{" "}
            {doc.changed_count} changed
          </p>
          {doc.confirmed ? (
            <span className={styles.confirmedPill}>Carry-over confirmed</span>
          ) : (
            <button
              type="button"
              className={styles.secondaryButton}
              disabled={confirming === doc.old_document_id}
              onClick={() => confirm(doc.old_document_id, doc.new_document_id)}
            >
              {confirming === doc.old_document_id ? "Confirming..." : "Confirm carry-over"}
            </button>
          )}
        </div>
      ))}
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}

function TieOutsSection({ data }: { data: AreaDetailData }) {
  if (data.tie_outs.length === 0) return null;
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Tie-outs</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Line</th>
            <th className={styles.num}>Engine value</th>
            <th className={styles.num}>Workpaper value</th>
            <th>Agrees</th>
          </tr>
        </thead>
        <tbody>
          {data.tie_outs.map((tieOut) => (
            <tr key={tieOut.line_key}>
              <td>{tieOut.label ?? tieOut.line_key}</td>
              <td className={`mono ${styles.num}`}>{formatValue(tieOut.engine_value)}</td>
              <td className={`mono ${styles.num}`}>{formatValue(tieOut.workpaper_value)}</td>
              <td className={tieOut.ok ? styles.ok : styles.breaks}>
                {tieOut.ok ? "✓" : `✗ (${tieOut.difference})`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function TimeBudgetSection({ scope }: { scope: string }) {
  const [budget, setBudget] = useState<AreaTimeBudget | null>(null);
  const [hours, setHours] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    apiFetch<TimeReport>("/api/time")
      .then((body) => setBudget(body.budget.find((row) => row.area === scope) ?? null))
      .catch(() => setBudget(null));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  async function logTime(event: React.FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError(null);
    try {
      await apiPost("/api/time", {
        area: scope,
        hours,
        date: new Date().toISOString().slice(0, 10),
      });
      setHours("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to log time");
    } finally {
      setWorking(false);
    }
  }

  if (!budget) return null;

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Time against budget</h2>
      <p>
        {budget.logged_hours} of {budget.budget_hours ?? "—"} hour(s) logged
        {budget.over_budget && <span className={styles.breaks}> · over budget</span>}
      </p>
      <form className={styles.formRow} onSubmit={logTime}>
        <label className={styles.field}>
          Log hours
          <input
            className={styles.input}
            type="number"
            step="0.25"
            min="0.25"
            required
            value={hours}
            onChange={(event) => setHours(event.target.value)}
          />
        </label>
        <button type="submit" className={styles.secondaryButton} disabled={working}>
          {working ? "Logging..." : "Log time"}
        </button>
      </form>
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}

type DetailRow = AreaDetailData["detail"][number];

// docs/UX.md S3: "Large detail (e.g., Form 8949's 302 lines): grouped by
// issuer and box, with a summary row per group ... expand to see lots."
// The area-detail API gives no explicit group field, but a line key's
// engine-assigned family (everything before its last dot segment, e.g.
// "F8949.D" for "F8949.D.M9") is exactly that grouping, and it's a
// structural property of the engine's own line-numbering, not a
// client-specific value. A family only becomes a collapsible group once
// it's actually large enough to need one; a handful of one-off lines
// (most scopes) still render as the plain flat table below.
const GROUP_THRESHOLD = 4;

function lineKeyFamily(lineKey: string): string {
  const parts = lineKey.split(".");
  return parts.length > 1 ? parts.slice(0, -1).join(".") : lineKey;
}

function groupDetailRows(rows: DetailRow[]): {
  groups: Array<{ key: string; rows: DetailRow[] }>;
  ungrouped: DetailRow[];
} {
  const byFamily = new Map<string, DetailRow[]>();
  for (const row of rows) {
    const key = lineKeyFamily(row.line_key);
    const list = byFamily.get(key) ?? [];
    list.push(row);
    byFamily.set(key, list);
  }
  const groups: Array<{ key: string; rows: DetailRow[] }> = [];
  const ungrouped: DetailRow[] = [];
  for (const [key, list] of byFamily) {
    if (list.length >= GROUP_THRESHOLD) groups.push({ key, rows: list });
    else ungrouped.push(...list);
  }
  return { groups, ungrouped };
}

function DetailTableRow({
  row,
  checked,
  onToggle,
}: {
  row: DetailRow;
  checked: boolean;
  onToggle: (claimKey: string) => void;
}) {
  return (
    <tr>
      <td>
        {row.claim_key && !row.verified && (
          <input
            type="checkbox"
            checked={checked}
            onChange={() => onToggle(row.claim_key as string)}
          />
        )}
      </td>
      <td>{row.label ?? row.line_key}</td>
      <td className={`mono ${styles.num}`}>
        <TraceableNumber lineKey={row.line_key}>{formatValue(row.value)}</TraceableNumber>
      </td>
      <td>
        <ProvenanceBadge kind={row.provenance_label} />
      </td>
      <td>
        <ReviewStateMarker state={row.verified ? "verified" : "unverified"} verifiedBy={row.verified_by} />
      </td>
    </tr>
  );
}

function DetailGroup({
  groupKey,
  rows,
  selected,
  onToggle,
}: {
  groupKey: string;
  rows: DetailRow[];
  selected: Set<string>;
  onToggle: (claimKey: string) => void;
}) {
  const verifiedCount = rows.filter((row) => row.verified).length;
  const total = rows.reduce((sum, row) => (typeof row.value === "number" ? sum + row.value : sum), 0);
  return (
    <details className={styles.detailGroup}>
      <summary className={styles.groupSummary}>
        <span className={`mono ${styles.groupLabel}`}>{groupKey}</span>
        <span className={styles.groupMeta}>{rows.length} lines</span>
        <span className={`mono ${styles.groupMeta}`}>{formatValue(total)} total</span>
        <span className={styles.groupMeta}>
          {verifiedCount} / {rows.length} verified
        </span>
      </summary>
      <div className={styles.groupBody}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th />
              <th>Line</th>
              <th className={styles.num}>Value</th>
              <th>Provenance</th>
              <th>Verified</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <DetailTableRow
                key={row.line_key}
                row={row}
                checked={row.claim_key ? selected.has(row.claim_key) : false}
                onToggle={onToggle}
              />
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function DetailSection({
  scope,
  data,
  onVerified,
}: {
  scope: string;
  data: AreaDetailData;
  onVerified: () => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [undoEventId, setUndoEventId] = useState<string | null>(null);

  const verifiable = useMemo(
    () => data.detail.filter((row) => row.claim_key && !row.verified),
    [data.detail],
  );

  const { groups, ungrouped } = useMemo(() => groupDetailRows(data.detail), [data.detail]);

  function toggle(claimKey: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(claimKey)) next.delete(claimKey);
      else next.add(claimKey);
      return next;
    });
  }

  async function bulkVerify() {
    setWorking(true);
    setError(null);
    try {
      const result = await apiPost<{ event_id: string }>(`/api/areas/${scope}/bulk-verify`, {
        claim_keys: Array.from(selected),
      });
      setUndoEventId(result.event_id);
      setSelected(new Set());
      onVerified();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to verify");
    } finally {
      setWorking(false);
    }
  }

  async function undo() {
    if (!undoEventId) return;
    setWorking(true);
    try {
      await apiPost(`/api/areas/${scope}/undo-bulk-verify`, { event_id: undoEventId });
      setUndoEventId(null);
      onVerified();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to undo");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Detail ({data.detail.length} lines)</h2>
      <div className={styles.bulkBar}>
        <button
          type="button"
          className={styles.secondaryButton}
          disabled={selected.size === 0 || working}
          onClick={bulkVerify}
        >
          Verify {selected.size || ""} selected
        </button>
        {undoEventId && (
          <button type="button" className={styles.secondaryButton} onClick={undo} disabled={working}>
            Undo
          </button>
        )}
      </div>
      {error && <p className={styles.error}>{error}</p>}
      {groups.map((group) => (
        <DetailGroup
          key={group.key}
          groupKey={group.key}
          rows={group.rows}
          selected={selected}
          onToggle={toggle}
        />
      ))}
      {ungrouped.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th />
              <th>Line</th>
              <th className={styles.num}>Value</th>
              <th>Provenance</th>
              <th>Verified</th>
            </tr>
          </thead>
          <tbody>
            {ungrouped.map((row) => (
              <DetailTableRow
                key={row.line_key}
                row={row}
                checked={row.claim_key ? selected.has(row.claim_key) : false}
                onToggle={toggle}
              />
            ))}
          </tbody>
        </table>
      )}
      {verifiable.length === 0 && data.detail.length > 0 && (
        <p className={styles.small}>Everything with a claim identity is verified.</p>
      )}
    </section>
  );
}

export function AreaDetail({ scope }: { scope: string }) {
  const [data, setData] = useState<AreaDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    apiFetch<AreaDetailData>(`/api/areas/${scope}`)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "failed to load"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  if (loading && !data) return <p className={styles.loadingState}>Loading...</p>;
  if (error) return <p className={styles.error}>{error}</p>;
  if (!data) return null;

  return (
    <div className={styles.page}>
      <SignOffHeader scope={scope} data={data} onSignedOff={load} />
      {data.blocking_reasons.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>What blocks sign-off</h2>
          <ul className={styles.disabledReasons}>
            {data.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      )}
      <ChangesSection scope={scope} data={data} onConfirmed={load} />
      <TieOutsSection data={data} />
      <TimeBudgetSection scope={scope} />
      <DetailSection scope={scope} data={data} onVerified={load} />
    </div>
  );
}
