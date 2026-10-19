"use client";

import { useEffect, useState } from "react";
import { closeTraceDrawer, useTraceDrawerLineKey } from "@/lib/traceDrawer";
import { TraceContent } from "@/components/TraceContent";
import styles from "./TraceDrawer.module.css";

/** The one Trace drawer instance for the whole app (docs/UX.md Layout).
 * `AppShell` renders this once; any `TraceableNumber` anywhere can open
 * it via `openTraceDrawer(lineKey)`. */
export function TraceDrawer() {
  const openedLineKey = useTraceDrawerLineKey();
  const [currentLineKey, setCurrentLineKey] = useState<string | null>(null);

  useEffect(() => {
    if (openedLineKey) setCurrentLineKey(openedLineKey);
  }, [openedLineKey]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && openedLineKey) closeTraceDrawer();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openedLineKey]);

  if (!openedLineKey || !currentLineKey) return null;

  return (
    <div className={styles.overlay} role="presentation" onClick={closeTraceDrawer}>
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label={`Trace ${currentLineKey}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.header}>
          <span className={styles.title}>Trace</span>
          <button type="button" className={styles.closeButton} onClick={closeTraceDrawer} autoFocus>
            Close (Esc)
          </button>
        </div>
        <div className={styles.body}>
          <TraceContent lineKey={currentLineKey} onNavigate={setCurrentLineKey} />
        </div>
      </aside>
    </div>
  );
}
