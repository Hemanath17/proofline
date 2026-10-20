"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { VersionDiffResponse, WhatIfsResponse } from "@/lib/types";
import styles from "@/components/Shared.module.css";

const VERSIONS = ["v1", "v2", "v3", "workpaper"] as const;

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (typeof value !== "string" && typeof value !== "number") return String(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function VersionDiffTab() {
  const [from, setFrom] = useState<string>("v1");
  const [to, setTo] = useState<string>("workpaper");
  const [onlyChanged, setOnlyChanged] = useState(true);
  const [data, setData] = useState<VersionDiffResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<VersionDiffResponse>(
      `/api/versions/diff?from=${from}&to=${to}&only_changed=${onlyChanged}`,
    )
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "failed to load"));
  }, [from, to, onlyChanged]);

  return (
    <section className={styles.section}>
      <div className={styles.formRow}>
        <label className={styles.field}>
          From
          <select className={styles.input} value={from} onChange={(e) => setFrom(e.target.value)}>
            {VERSIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          To
          <select className={styles.input} value={to} onChange={(e) => setTo(e.target.value)}>
            {VERSIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={onlyChanged}
            onChange={(e) => setOnlyChanged(e.target.checked)}
          />
          Only changed
        </label>
      </div>
      {error && <p className={styles.error}>{error}</p>}
      {data && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Line</th>
              <th>Rule</th>
              <th className={styles.num}>Old</th>
              <th className={styles.num}>New</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((line) => (
              <tr key={line.line_key}>
                <td>{line.label ?? line.line_key}</td>
                <td className="mono">{line.rule ?? "—"}</td>
                <td className={`mono ${styles.num}`}>{formatValue(line.old_value)}</td>
                <td className={`mono ${styles.num}`}>{formatValue(line.new_value)}</td>
                <td>{line.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && data.lines.length === 0 && (
        <p className={styles.emptyState}>No changed lines between these two versions.</p>
      )}
    </section>
  );
}

function WhatIfsTab() {
  const [data, setData] = useState<WhatIfsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<WhatIfsResponse>("/api/what-ifs")
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "failed to load"));
  }, []);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!data) return <p className={styles.loadingState}>Loading...</p>;

  return (
    <>
      {data.alternatives.map((alternative) => (
        <section key={alternative.id} className={styles.section}>
          <h2 className={styles.sectionTitle}>
            {alternative.description ?? alternative.id} <span className={styles.pill}>What-if</span>
          </h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Line</th>
                <th className={styles.num}>What-if value</th>
                <th className={styles.num}>Current workpaper value</th>
              </tr>
            </thead>
            <tbody>
              {alternative.changed_lines.map((line) => (
                <tr key={line.line_key}>
                  <td className="mono">{line.line_key}</td>
                  <td className={`mono ${styles.num}`}>{formatValue(line.what_if_new)}</td>
                  <td className={`mono ${styles.num}`}>{formatValue(line.current_workpaper_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </>
  );
}

export default function ReturnPage() {
  const [tab, setTab] = useState<"versions" | "whatifs">("versions");

  return (
    <div className={styles.page}>
      <h1>Return</h1>
      <nav className={styles.tabs}>
        <button
          type="button"
          className={`${styles.tab} ${tab === "versions" ? styles.tabActive : ""}`}
          onClick={() => setTab("versions")}
        >
          Comparing versions
        </button>
        <button
          type="button"
          className={`${styles.tab} ${tab === "whatifs" ? styles.tabActive : ""}`}
          onClick={() => setTab("whatifs")}
        >
          What-ifs
        </button>
      </nav>
      {tab === "versions" ? <VersionDiffTab /> : <WhatIfsTab />}
    </div>
  );
}
