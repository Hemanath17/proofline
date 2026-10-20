"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import { useCurrentActor } from "@/lib/session";
import type { DueDiligenceChecklist, Judgment, OutsideFilingItem } from "@/lib/types";
import styles from "@/components/Shared.module.css";

function JudgmentsSection() {
  const { actorId } = useCurrentActor();
  const [judgments, setJudgments] = useState<Judgment[]>([]);
  const [authority, setAuthority] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [isElection, setIsElection] = useState(false);
  const [whatIfId, setWhatIfId] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    apiFetch<{ judgments: Judgment[] }>("/api/judgments")
      .then((body) => setJudgments(body.judgments))
      .catch(() => setJudgments([]));
  }

  useEffect(() => {
    load();
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError(null);
    try {
      await apiPost("/api/judgments", {
        authority,
        approved_by: actorId,
        reasoning,
        is_election: isElection,
        what_if_id: isElection ? whatIfId : null,
      });
      setAuthority("");
      setReasoning("");
      setIsElection(false);
      setWhatIfId("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to record");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Judgments and elections ({judgments.length})</h2>
      {judgments.map((judgment) => (
        <div key={judgment.id} className={styles.card}>
          <span>{judgment.reasoning}</span>
          <span className={styles.small}>
            {judgment.authority} · approved by {judgment.approved_by}
            {judgment.is_election && ` · election (${judgment.what_if_id})`}
          </span>
        </div>
      ))}
      <form className={styles.formRow} onSubmit={submit}>
        <label className={styles.field}>
          Authority relied on
          <input className={styles.input} required value={authority} onChange={(e) => setAuthority(e.target.value)} />
        </label>
        <label className={styles.field}>
          Reasoning
          <input className={styles.input} required value={reasoning} onChange={(e) => setReasoning(e.target.value)} />
        </label>
        <label className={styles.field} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={isElection} onChange={(e) => setIsElection(e.target.checked)} />
          Election
        </label>
        {isElection && (
          <label className={styles.field}>
            What-if id
            <input className={styles.input} required value={whatIfId} onChange={(e) => setWhatIfId(e.target.value)} />
          </label>
        )}
        <button type="submit" className={styles.secondaryButton} disabled={working}>
          {working ? "Recording..." : "Record"}
        </button>
      </form>
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}

function DueDiligenceSection() {
  const [data, setData] = useState<DueDiligenceChecklist | null>(null);

  useEffect(() => {
    apiFetch<DueDiligenceChecklist>("/api/due-diligence")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>
        Due diligence (Form 8867){" "}
        <span className={data.done ? styles.ok : styles.breaks}>
          {data.done ? "Done" : "Not yet confirmed"}
        </span>
      </h2>
      {data.checklist.map((item) => (
        <p key={item.item} className={styles.small}>
          {item.description}
        </p>
      ))}
    </section>
  );
}

function OutsideFilingsSection() {
  const [items, setItems] = useState<OutsideFilingItem[]>([]);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    apiFetch<{ items: OutsideFilingItem[] }>("/api/outside-filings")
      .then((body) => setItems(body.items))
      .catch(() => setItems([]));
  }

  useEffect(() => {
    load();
  }, []);

  async function confirm(item: string, decision: string) {
    setWorking(item);
    setError(null);
    try {
      await apiPost(`/api/outside-filings/${item}/confirm`, {
        decision,
        note: `marked ${decision} from the outside-filings screen`,
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to confirm");
    } finally {
      setWorking(null);
    }
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Outside filings</h2>
      {items.map((item) => (
        <div key={item.item} className={styles.card}>
          <span>{item.label}</span>
          <span className={styles.small}>{item.note}</span>
          {item.decided ? (
            <span className={styles.ok}>
              {item.decision} · {item.decided_by}
            </span>
          ) : (
            <div className={styles.formRow}>
              {["filed", "not_required", "client_responsible", "open"].map((decision) => (
                <button
                  key={decision}
                  type="button"
                  className={styles.secondaryButton}
                  disabled={working === item.item}
                  onClick={() => confirm(item.item, decision)}
                >
                  {decision}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}

export default function JudgmentsPage() {
  return (
    <div className={styles.page}>
      <h1>Judgments and filings</h1>
      <JudgmentsSection />
      <DueDiligenceSection />
      <OutsideFilingsSection />
    </div>
  );
}
