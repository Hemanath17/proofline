"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import { JsonValue } from "@/components/JsonValue";
import styles from "@/components/Shared.module.css";

/** The sixteen CPA record views (R01-R16, docs/PLAN.md Step 9) -- each a
 * view over data Steps 1-8 already computed, so one generic browser
 * (select a view, render it with `JsonValue`) rather than sixteen
 * bespoke page layouts for what is, functionally, sixteen read-only
 * reports. */
const VIEWS: Array<{ id: string; label: string; path: string }> = [
  { id: "r01", label: "R01 Return summary vs last year", path: "/api/records/return-summary" },
  { id: "r02", label: "R02 Tax computation", path: "/api/records/tax-computation" },
  { id: "r03", label: "R03 Area summaries", path: "/api/records/area-summaries" },
  { id: "r04", label: "R04 Document index", path: "/api/records/documents" },
  { id: "r05", label: "R05 Depreciation by asset", path: "/api/records/depreciation" },
  { id: "r06", label: "R06 Sales detail (Form 8949)", path: "/api/records/sales-detail" },
  { id: "r07", label: "R07 Books to tax", path: "/api/records/books-to-tax" },
  { id: "r08", label: "R08 Rentals and passive losses", path: "/api/records/rentals-passive" },
  { id: "r09", label: "R09 K-1 lines", path: "/api/records/k1-lines" },
  { id: "r10", label: "R10 Retirement and foreign items", path: "/api/records/retirement-foreign" },
  { id: "r11", label: "R11 Deductions and credits", path: "/api/records/deductions-credits" },
  { id: "r12", label: "R12 Payments", path: "/api/records/payments" },
  { id: "r13", label: "R13 State split", path: "/api/records/state-split" },
  { id: "r14", label: "R14 Carryovers", path: "/api/records/carryovers" },
  { id: "r15", label: "R15 Basis by year", path: "/api/records/basis" },
  { id: "r16", label: "R16 Prior preparer vs. what we changed", path: "/api/records/prior-preparer" },
];

export default function RecordsPage() {
  const [viewId, setViewId] = useState(VIEWS[0].id);
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const view = VIEWS.find((v) => v.id === viewId) ?? VIEWS[0];

  useEffect(() => {
    apiFetch<unknown>(view.path)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "failed to load"));
  }, [view.path]);

  return (
    <div className={styles.page}>
      <h1>Records</h1>
      <label className={styles.field}>
        View
        <select className={styles.input} value={viewId} onChange={(e) => setViewId(e.target.value)}>
          {VIEWS.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
            </option>
          ))}
        </select>
      </label>
      {error && <p className={styles.error}>{error}</p>}
      {data !== null && (
        <section className={styles.section}>
          <JsonValue value={data} />
        </section>
      )}
    </div>
  );
}
