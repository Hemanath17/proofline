"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { apiFetch } from "@/lib/api-client";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { KeyboardLayer } from "@/components/KeyboardLayer";
import { CommandMenu } from "@/components/CommandMenu";
import { TraceDrawer } from "@/components/TraceDrawer";
import { TourOverlay } from "@/components/Tour/TourOverlay";
import { useCurrentActor } from "@/lib/session";
import styles from "./AppShell.module.css";

const STAFF_RAIL_ITEMS: Array<{ href: string; label: string }> = [
  { href: "/queue", label: "Queue" },
  { href: "/areas", label: "Areas" },
  { href: "/documents", label: "Documents" },
  { href: "/return", label: "Return" },
  { href: "/records", label: "Records" },
  { href: "/judgments", label: "Judgments" },
  { href: "/activity", label: "Activity" },
];

// S5 (Step 9): the client workspace is a genuinely smaller surface, not
// the staff rail with fewer items -- a client gets exactly one
// destination, matching the one small API surface they can actually call.
const CLIENT_RAIL_ITEMS: Array<{ href: string; label: string }> = [
  { href: "/client", label: "My return" },
];

type ReturnInfo = {
  household_names: string[];
  tax_year: number;
  engine_version: string;
};

function useReturnInfo(skip: boolean): ReturnInfo | null {
  const [info, setInfo] = useState<ReturnInfo | null>(null);
  useEffect(() => {
    if (skip) return;
    let cancelled = false;
    apiFetch<ReturnInfo>("/api/return")
      .then((body) => {
        if (!cancelled) setInfo(body);
      })
      .catch(() => {
        if (!cancelled) setInfo(null);
      });
    return () => {
      cancelled = true;
    };
  }, [skip]);
  return info;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { actor } = useCurrentActor();
  const isClient = actor?.role === "client";
  // /api/return is a staff-surface route (require_non_client, Step 10 Part
  // 0) -- the client workspace never calls it, same as every other
  // staff-surface endpoint.
  const info = useReturnInfo(isClient);
  const railItems = isClient ? CLIENT_RAIL_ITEMS : STAFF_RAIL_ITEMS;

  // The landing page (Part A of the tour/landing addition) is a marketing
  // page for a first-time visitor, not another app screen -- it renders
  // outside this chrome entirely.
  if (pathname === "/") return <>{children}</>;

  return (
    <div className={styles.shell}>
      <aside className={`${styles.rail} ${collapsed ? styles.railCollapsed : ""}`}>
        <div className={styles.railHeader}>
          {!collapsed && (
            <div className={styles.returnLabel}>
              <span className={styles.returnName}>
                {info ? info.household_names.join(" & ") : isClient ? "Your return" : "Loading..."}
              </span>
              <span className={styles.returnYear}>{info ? `${info.tax_year} return` : ""}</span>
            </div>
          )}
          <button
            type="button"
            className={styles.collapseButton}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        <nav aria-label="Primary">
          <ul className={styles.railList}>
            {railItems.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`${styles.railLink} ${active ? styles.railLinkActive : ""}`}
                  >
                    {!collapsed ? item.label : item.label[0]}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
      <div className={styles.main}>
        <header className={styles.topBar}>
          <div className={styles.topBarLeft}>
            <span className={styles.appName}>Proofline</span>
            {info && <span className={`${styles.engineBadge} mono`}>{info.engine_version}</span>}
          </div>
          <div className={styles.topBarRight}>
            {!isClient && (
              <button
                type="button"
                className={styles.searchStub}
                onClick={() => window.dispatchEvent(new Event("proofline:open-command-menu"))}
                aria-label="Open command menu"
              >
                Search... <span className="mono">Cmd/Ctrl+K</span>
              </button>
            )}
            <RoleSwitcher />
          </div>
        </header>
        <main className={styles.content}>{children}</main>
      </div>
      <KeyboardLayer />
      <CommandMenu />
      <TraceDrawer />
      {!isClient && (
        <Suspense fallback={null}>
          <TourOverlay />
        </Suspense>
      )}
    </div>
  );
}
