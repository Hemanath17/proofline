"use client";

import { useEffect, useState } from "react";

const OPEN_EVENT = "proofline:open-trace-drawer";
const CLOSE_EVENT = "proofline:close-trace-drawer";

export function openTraceDrawer(lineKey: string): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: lineKey }));
}

export function closeTraceDrawer(): void {
  window.dispatchEvent(new Event(CLOSE_EVENT));
}

/** Any number anywhere opens this same drawer (docs/UX.md Layout: "Any
 * number anywhere is clickable and opens the Trace drawer from the right
 * without leaving the page"). One global piece of state, read by the one
 * `TraceDrawer` instance `AppShell` renders. */
export function useTraceDrawerLineKey(): string | null {
  const [lineKey, setLineKey] = useState<string | null>(null);

  useEffect(() => {
    function onOpen(event: Event) {
      setLineKey((event as CustomEvent<string>).detail);
    }
    function onClose() {
      setLineKey(null);
    }
    window.addEventListener(OPEN_EVENT, onOpen);
    window.addEventListener(CLOSE_EVENT, onClose);
    return () => {
      window.removeEventListener(OPEN_EVENT, onOpen);
      window.removeEventListener(CLOSE_EVENT, onClose);
    };
  }, []);

  return lineKey;
}
