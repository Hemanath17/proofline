"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ShortcutSheet } from "@/components/ShortcutSheet";

const STORAGE_KEY = "proofline.shortcutsEnabled";

export function shortcutsEnabled(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(STORAGE_KEY) !== "false";
}

export function setShortcutsEnabled(enabled: boolean): void {
  window.localStorage.setItem(STORAGE_KEY, String(enabled));
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
}

/** The global part of docs/UX.md's keyboard layer: `G Q` / `G A` / `G D`
 * to navigate, `?` for the shortcut sheet. Per-list `J`/`K`/`Enter`/`Esc`
 * live in the screens that have a list (useListNav below), since only one
 * list is ever focused at a time. Shortcuts can be turned off entirely
 * (WCAG 2.1.4) via the settings this component also renders. */
export function KeyboardLayer() {
  const router = useRouter();
  const [sheetOpen, setSheetOpen] = useState(false);
  const pendingG = useRef(false);
  const pendingGTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!shortcutsEnabled()) return;
      if (isTypingTarget(event.target)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      if (pendingG.current) {
        pendingG.current = false;
        if (pendingGTimer.current) clearTimeout(pendingGTimer.current);
        if (event.key === "q") {
          event.preventDefault();
          router.push("/queue");
        } else if (event.key === "a") {
          event.preventDefault();
          router.push("/areas");
        } else if (event.key === "d") {
          event.preventDefault();
          router.push("/documents");
        }
        return;
      }

      if (event.key === "g") {
        pendingG.current = true;
        pendingGTimer.current = setTimeout(() => {
          pendingG.current = false;
        }, 800);
        return;
      }

      if (event.key === "?") {
        event.preventDefault();
        setSheetOpen((open) => !open);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);

  return <ShortcutSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />;
}
