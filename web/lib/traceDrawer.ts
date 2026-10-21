"use client";

import { useEffect, useState } from "react";

const OPEN_EVENT = "proofline:open-trace-drawer";
const CLOSE_EVENT = "proofline:close-trace-drawer";

/** What the one Trace drawer instance is currently showing: a line's full
 * trace (S4), or a single evidence reference's preview (S2's evidence
 * cards and the proposal's evidence picker). One drawer, one shell, two
 * content kinds -- not two drawers. */
export type DrawerTarget =
  | { kind: "line"; lineKey: string }
  | { kind: "evidence"; ref: string };

export function openTrace(target: DrawerTarget): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: target }));
}

/** Any number anywhere opens this same drawer (docs/UX.md Layout: "Any
 * number anywhere is clickable and opens the Trace drawer from the right
 * without leaving the page"). */
export function openTraceDrawer(lineKey: string): void {
  openTrace({ kind: "line", lineKey });
}

/** Any evidence reference anywhere opens the same drawer, showing a
 * preview instead of a full line trace (docs/UX.md S2 "a click opens the
 * Trace drawer"). */
export function openEvidencePreview(ref: string): void {
  openTrace({ kind: "evidence", ref });
}

export function closeTraceDrawer(): void {
  window.dispatchEvent(new Event(CLOSE_EVENT));
}

export function useTraceDrawerTarget(): DrawerTarget | null {
  const [target, setTarget] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    function onOpen(event: Event) {
      setTarget((event as CustomEvent<DrawerTarget>).detail);
    }
    function onClose() {
      setTarget(null);
    }
    window.addEventListener(OPEN_EVENT, onOpen);
    window.addEventListener(CLOSE_EVENT, onClose);
    return () => {
      window.removeEventListener(OPEN_EVENT, onOpen);
      window.removeEventListener(CLOSE_EVENT, onClose);
    };
  }, []);

  return target;
}
