"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import type { AreaDetail } from "@/lib/types";
import styles from "./page.module.css";

const SCOPES: Array<{ key: string; label: string }> = [
  { key: "identity", label: "Identity and household" },
  { key: "wages", label: "Wages and stock compensation" },
  { key: "investments", label: "Investments and digital assets" },
  { key: "business", label: "Business" },
  { key: "rentals", label: "Rentals and sale" },
  { key: "pass_throughs", label: "Pass-throughs and basis" },
  { key: "deductions_credits", label: "Deductions and credits" },
  { key: "california", label: "California" },
  { key: "tax_computation", label: "Tax computation" },
];

export default function AreasPage() {
  const [byScope, setByScope] = useState<Record<string, AreaDetail>>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      SCOPES.map((scope) =>
        apiFetch<AreaDetail>(`/api/areas/${scope.key}`).then((data) => [scope.key, data] as const),
      ),
    ).then((results) => {
      if (!cancelled) setByScope(Object.fromEntries(results));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1>Areas</h1>
      <div className={styles.list}>
        {SCOPES.map((scope) => {
          const data = byScope[scope.key];
          const changePending =
            data?.changes_since_sign_off !== null &&
            (data?.changes_since_sign_off?.value_changed ||
              data?.changes_since_sign_off?.scope_changed ||
              data?.changes_since_sign_off?.decision_changed ||
              data?.changes_since_sign_off?.documents.some((d) => !d.confirmed));
          const stateClass = !data || !data.sign_off
            ? styles.stateNeutral
            : changePending
              ? styles.stateAmber
              : styles.stateGreen;
          const stateLabel = !data
            ? "Loading…"
            : data.sign_off
              ? changePending
                ? `Signed v${data.sign_off.version} · change pending`
                : `Signed v${data.sign_off.version}`
              : "Not signed";
          return (
            <Link key={scope.key} href={`/areas/${scope.key}`} className={styles.row}>
              <span className={styles.name}>{scope.label}</span>
              <span className={`${styles.state} ${stateClass}`}>{stateLabel}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
