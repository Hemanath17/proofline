"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { NotificationsResponse } from "@/lib/types";
import { caseStatusLabel } from "@/components/Badges";
import styles from "@/components/Shared.module.css";

/** B14, B26: the notifications feed -- needs-me cases, what changed since
 * you last looked, and the packet's own deadlines. Polling (a plain
 * fetch on mount), not a websocket, matching docs/UX.md. */
export default function ActivityPage() {
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<NotificationsResponse>("/api/notifications")
      .then((body) => {
        if (!cancelled) setData(body);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "failed to load");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={styles.page}>
      <h1>Activity</h1>
      {error && <p className={styles.error}>{error}</p>}
      {!data && !error && <p className={styles.emptyState}>Loading...</p>}
      {data && (
        <>
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Needs me ({data.needs_me.length})</h2>
            {data.needs_me.length === 0 && (
              <p className={styles.emptyState}>Nothing needs you right now.</p>
            )}
            {data.needs_me.map((item) => (
              <Link key={item.entity_id} href={`/cases/${item.entity_id}`} className={styles.card}>
                <span>{item.label}</span>
                <span className={styles.small}>
                  {item.scope} · {item.status ? caseStatusLabel(item.status) : ""}
                </span>
              </Link>
            ))}
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>
              Changed since you last looked ({data.changed.length})
            </h2>
            {data.changed.length === 0 && (
              <p className={styles.emptyState}>Nothing you&apos;ve visited has changed.</p>
            )}
            {data.changed.map((item) => (
              <Link
                key={item.entity_id}
                href={item.entity_type === "case" ? `/cases/${item.entity_id}` : `/documents/${item.entity_id}`}
                className={styles.card}
              >
                <span>{item.label}</span>
                <span className={styles.small}>
                  {item.entity_type} · changed{" "}
                  {item.changed_at ? new Date(item.changed_at).toLocaleString() : ""}
                </span>
              </Link>
            ))}
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Deadlines</h2>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>What</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.deadlines.map((deadline) => (
                  <tr key={deadline.label}>
                    <td>{deadline.label}</td>
                    <td className="mono">{deadline.date}</td>
                    <td className={deadline.overdue ? styles.breaks : undefined}>
                      {deadline.overdue
                        ? `${Math.abs(deadline.days_remaining)} day(s) overdue`
                        : `${deadline.days_remaining} day(s) remaining`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
