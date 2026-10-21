"use client";

import { useEffect, useState } from "react";
import { closeTraceDrawer, useTraceDrawerTarget, type DrawerTarget } from "@/lib/traceDrawer";
import { TraceContent } from "@/components/TraceContent";
import { EvidenceContent } from "@/components/EvidenceContent";
import styles from "./TraceDrawer.module.css";

/** The one Trace drawer instance for the whole app (docs/UX.md Layout).
 * `AppShell` renders this once; any `TraceableNumber` or evidence
 * reference anywhere can open it via `openTraceDrawer(lineKey)` or
 * `openEvidencePreview(ref)`. One shell, two content kinds. */
export function TraceDrawer() {
  const openedTarget = useTraceDrawerTarget();
  const [currentTarget, setCurrentTarget] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    if (openedTarget) setCurrentTarget(openedTarget);
  }, [openedTarget]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && openedTarget) closeTraceDrawer();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openedTarget]);

  if (!openedTarget || !currentTarget) return null;

  const title = currentTarget.kind === "line" ? "Trace" : "Evidence";
  const label =
    currentTarget.kind === "line"
      ? `Trace ${currentTarget.lineKey}`
      : `Evidence ${currentTarget.ref}`;

  return (
    <div className={styles.overlay} role="presentation" onClick={closeTraceDrawer}>
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <button type="button" className={styles.closeButton} onClick={closeTraceDrawer} autoFocus>
            Close (Esc)
          </button>
        </div>
        <div className={styles.body}>
          {currentTarget.kind === "line" ? (
            <TraceContent
              lineKey={currentTarget.lineKey}
              onNavigate={(lineKey) => setCurrentTarget({ kind: "line", lineKey })}
            />
          ) : (
            <EvidenceContent reference={currentTarget.ref} />
          )}
        </div>
      </aside>
    </div>
  );
}
