"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import { CaseStatusPill, severityLabel, TaxEffectDisplay } from "@/components/Badges";
import { CaseDetailPanel } from "@/components/CaseDetailPanel";
import type { CaseRow, QueueResponse } from "@/lib/types";
import styles from "./page.module.css";

const TABS: Array<{ key: string; label: string }> = [
  { key: "needs_me", label: "Needs me" },
  { key: "all_open", label: "All open" },
  { key: "waiting_on_client", label: "Waiting on client" },
  { key: "resolved", label: "Resolved" },
];

type VisibleGroup = { severity: string; totalFederal: number; rows: CaseRow[] };

function age(createdAt: string): string {
  const days = Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

export default function QueuePage() {
  return (
    <Suspense fallback={null}>
      <QueueView />
    </Suspense>
  );
}

function QueueView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") ?? "needs_me";
  const selectedCaseId = searchParams.get("case");

  const [queue, setQueue] = useState<QueueResponse | null>(null);
  const [filter, setFilter] = useState("");
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const filterInputRef = useRef<HTMLInputElement>(null);

  function load() {
    apiFetch<QueueResponse>(`/api/cases?tab=${tab}`).then(setQueue);
  }

  useEffect(load, [tab]);

  const visibleGroups: VisibleGroup[] = useMemo(() => {
    if (!queue) return [];
    const needle = filter.trim().toLowerCase();
    return queue.groups
      .map((group) => ({
        severity: group.severity,
        totalFederal: Number(group.total_tax_effect.federal),
        rows: needle
          ? group.cases.filter((row) => (row.title ?? "").toLowerCase().includes(needle))
          : group.cases,
      }))
      .filter((group) => group.rows.length > 0);
  }, [queue, filter]);

  const flatRows = useMemo(() => visibleGroups.flatMap((group) => group.rows), [visibleGroups]);

  function setTab(nextTab: string) {
    router.push(`/queue?tab=${nextTab}`);
  }

  function select(caseId: string | null) {
    const params = new URLSearchParams();
    params.set("tab", tab);
    if (caseId) params.set("case", caseId);
    router.push(`/queue?${params.toString()}`);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (document.activeElement === filterInputRef.current) {
        if (event.key === "Escape") filterInputRef.current?.blur();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "j") {
        event.preventDefault();
        setFocusedIndex((index) => Math.min(index + 1, flatRows.length - 1));
      } else if (event.key === "k") {
        event.preventDefault();
        setFocusedIndex((index) => Math.max(index - 1, 0));
      } else if (event.key === "Enter") {
        const row = flatRows[focusedIndex];
        if (row) select(row.case_id);
      } else if (event.key === "Escape") {
        select(null);
      } else if (event.key === "/") {
        event.preventDefault();
        filterInputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flatRows, focusedIndex, tab]);

  async function sync() {
    setSyncing(true);
    try {
      await apiPost("/api/cases/sync");
      load();
    } catch (err) {
      // A toast system is later work; this keeps the sync button honest
      // about a failure rather than swallowing it silently.
      console.error(err instanceof ApiError ? err.detail : err);
    } finally {
      setSyncing(false);
    }
  }

  const waitingOnClientCount = queue?.counts.waiting_on_client ?? 0;

  return (
    <div className={styles.layout}>
      <div className={styles.listPane}>
        <div className={styles.listHeader}>
          <nav className={styles.tabs} aria-label="Queue tabs">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`${styles.tab} ${tab === item.key ? styles.tabActive : ""}`}
                onClick={() => setTab(item.key)}
              >
                {item.label}
                {queue && <span className={styles.tabCount}>{queue.counts[item.key] ?? 0}</span>}
              </button>
            ))}
          </nav>
          <div className={styles.listHeaderRight}>
            <input
              ref={filterInputRef}
              className={styles.filterInput}
              placeholder="Filter ( / )"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
            <button type="button" className={styles.syncButton} onClick={sync} disabled={syncing}>
              {syncing ? "Syncing..." : "Sync cases"}
            </button>
          </div>
        </div>

        {queue && visibleGroups.length === 0 && (
          <p className={styles.emptyState}>
            Nothing needs you.{" "}
            {waitingOnClientCount > 0
              ? `${waitingOnClientCount} case${waitingOnClientCount === 1 ? "" : "s"} are waiting on the client.`
              : ""}
          </p>
        )}

        {visibleGroups.map((group) => (
          <section key={group.severity} className={styles.group}>
            <h2 className={styles.groupHeader}>
              {severityLabel(group.severity)} · {group.rows.length}
              <span className={styles.groupTotal}>
                {" "}
                · total {Math.round(Math.abs(group.totalFederal)).toLocaleString()} federal
              </span>
            </h2>
            <ul className={styles.rowList}>
              {group.rows.map((row) => {
                const index = flatRows.indexOf(row);
                return (
                  <li key={row.case_id}>
                    <button
                      type="button"
                      className={`${styles.row} ${index === focusedIndex ? styles.rowFocused : ""} ${
                        selectedCaseId === row.case_id ? styles.rowSelected : ""
                      }`}
                      onClick={() => {
                        setFocusedIndex(index);
                        select(row.case_id);
                      }}
                    >
                      <span className={styles.unreadSlot}>
                        {row.changed_since_last_seen && (
                          <span className={styles.unreadDot} aria-label="Changed" />
                        )}
                      </span>
                      <div className={styles.rowMain}>
                        <span className={styles.rowTitle}>{row.title}</span>
                        <span className={styles.rowWhy}>{row.why_it_here}</span>
                      </div>
                      <span className={styles.rowArea}>{row.scope}</span>
                      <span className={styles.taxEffectSlot}>
                        {row.tax_effect && (
                          <TaxEffectDisplay
                            federal={row.tax_effect.federal}
                            california={row.tax_effect.california}
                            kind={row.tax_effect.kind}
                            direction={row.tax_effect.direction}
                          />
                        )}
                      </span>
                      <CaseStatusPill status={row.status} />
                      <span className={styles.rowAssignee}>{row.assignee_id ?? "unassigned"}</span>
                      <span className={styles.rowAge}>{age(row.created_at)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      <div className={styles.detailPane}>
        {selectedCaseId ? (
          <CaseDetailPanel caseId={selectedCaseId} />
        ) : (
          <p className={styles.detailPlaceholder}>Select a case to see it here.</p>
        )}
      </div>
    </div>
  );
}
