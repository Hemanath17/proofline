"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import type {
  ClientDocument,
  ClientPackageSummary,
  ClientQuestionThread,
  ClientSummary,
} from "@/lib/types";
import styles from "@/components/Shared.module.css";

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

// A positive balance is owed; a negative one is an overpayment coming
// back -- the sign is a real accounting convention here, not a guess at
// this client's own numbers, so turning it into plain words is safe.
function formatBalance(value: unknown): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) return formatValue(value);
  const whole = Math.round(Math.abs(amount)).toLocaleString("en-US");
  return amount < 0 ? `Refund of $${whole}` : `You owe $${whole}`;
}

function SummaryTab() {
  const [data, setData] = useState<ClientSummary | null>(null);

  useEffect(() => {
    apiFetch<ClientSummary>("/api/client/summary").then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <p className={styles.emptyState}>Loading...</p>;

  return (
    <section className={styles.section}>
      <div className={styles.card}>
        <span className={styles.sectionTitle}>Federal</span>
        <span className="mono">{formatBalance(data.federal.balance_due)}</span>
        <span className={styles.pill}>{data.federal.label}</span>
      </div>
      <div className={styles.card}>
        <span className={styles.sectionTitle}>California</span>
        <span className="mono">{formatBalance(data.california.balance_due)}</span>
        <span className={styles.pill}>{data.california.label}</span>
      </div>
    </section>
  );
}

function QuestionsTab() {
  const [threads, setThreads] = useState<ClientQuestionThread[]>([]);

  useEffect(() => {
    apiFetch<{ threads: ClientQuestionThread[] }>("/api/client/questions")
      .then((body) => setThreads(body.threads))
      .catch(() => setThreads([]));
  }, []);

  if (threads.length === 0) {
    return <p className={styles.emptyState}>No questions from your preparer yet.</p>;
  }

  return (
    <section className={styles.section}>
      {threads.map((thread) => (
        <div key={thread.case_id} className={styles.card}>
          <span className={styles.sectionTitle}>Question</span>
          <span>{thread.question}</span>
          {thread.answer ? (
            <>
              <span className={styles.sectionTitle}>Your answer</span>
              <span>{thread.answer}</span>
            </>
          ) : (
            <span className={styles.breaks}>Awaiting your answer</span>
          )}
        </div>
      ))}
    </section>
  );
}

function DocumentsTab() {
  const [documents, setDocuments] = useState<ClientDocument[]>([]);

  useEffect(() => {
    apiFetch<{ documents: ClientDocument[] }>("/api/client/documents")
      .then((body) => setDocuments(body.documents))
      .catch(() => setDocuments([]));
  }, []);

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Received</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((document) => (
          <tr key={document.id}>
            <td>{document.title}</td>
            <td>{document.document_type}</td>
            <td className="mono">{document.received_at ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SignTab() {
  const [pkg, setPkg] = useState<ClientPackageSummary | null>(null);
  const [taxpayerPin, setTaxpayerPin] = useState("");
  const [spousePin, setSpousePin] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signed, setSigned] = useState(false);

  useEffect(() => {
    apiFetch<ClientPackageSummary>("/api/client/package").then(setPkg).catch(() => setPkg(null));
  }, []);

  async function sign(event: React.FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError(null);
    try {
      await apiPost("/api/filing/authorize", {
        pins: { taxpayer: taxpayerPin, spouse: spousePin },
      });
      setSigned(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "failed to sign");
    } finally {
      setWorking(false);
    }
  }

  if (!pkg) return <p className={styles.emptyState}>Loading...</p>;

  return (
    <section className={styles.section}>
      <p>This signs exactly this package -- engine {pkg.engine_version}.</p>
      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
        <dt className={styles.small}>Package reference</dt>
        <dd className="mono">{pkg.reference}</dd>
        <dt className={styles.small}>Amounts fingerprint</dt>
        <dd className="mono">{pkg.amounts_fingerprint}</dd>
        <dt className={styles.small}>Identity fingerprint</dt>
        <dd className="mono">{pkg.identity_fingerprint}</dd>
      </dl>
      {signed ? (
        <p className={styles.ok}>Signed. Your signature is tied to this exact package.</p>
      ) : (
        <form className={styles.formRow} onSubmit={sign}>
          <label className={styles.field}>
            Taxpayer PIN
            <input
              className={styles.input}
              type="password"
              required
              value={taxpayerPin}
              onChange={(e) => setTaxpayerPin(e.target.value)}
            />
          </label>
          <label className={styles.field}>
            Spouse PIN
            <input
              className={styles.input}
              type="password"
              required
              value={spousePin}
              onChange={(e) => setSpousePin(e.target.value)}
            />
          </label>
          <button type="submit" className={styles.primaryButton} disabled={working}>
            {working ? "Signing..." : "Approve and sign"}
          </button>
        </form>
      )}
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}

export default function ClientWorkspacePage() {
  const [tab, setTab] = useState<"summary" | "questions" | "documents" | "sign">("summary");

  const tabs: Array<{ id: typeof tab; label: string }> = [
    { id: "summary", label: "Summary" },
    { id: "questions", label: "Your questions" },
    { id: "documents", label: "Your documents" },
    { id: "sign", label: "Approve and sign" },
  ];

  return (
    <div className={styles.page}>
      <h1>Your return</h1>
      <nav className={styles.tabs}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "summary" && <SummaryTab />}
      {tab === "questions" && <QuestionsTab />}
      {tab === "documents" && <DocumentsTab />}
      {tab === "sign" && <SignTab />}
    </div>
  );
}
