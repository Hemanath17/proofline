"use client";

import { openTraceDrawer } from "@/lib/traceDrawer";
import styles from "./TraceableNumber.module.css";

/** Wraps any rendered line value so clicking it opens the Trace drawer
 * (docs/UX.md Layout: "Any number anywhere is clickable..."). Used
 * wherever a screen shows a value that traces back to a packet line key
 * -- Step 7's area/detail tables are the heaviest user of this. */
export function TraceableNumber({
  lineKey,
  children,
}: {
  lineKey: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`mono ${styles.button}`}
      onClick={() => openTraceDrawer(lineKey)}
      title={`Trace ${lineKey}`}
    >
      {children}
    </button>
  );
}
