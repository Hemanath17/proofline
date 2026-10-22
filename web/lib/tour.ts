"use client";

import { apiFetch } from "@/lib/api-client";
import type { CaseRow, QueueResponse } from "@/lib/types";

const SEEN_KEY = "proofline.tourSeen";
export const START_TOUR_EVENT = "proofline:start-tour";

/** Same one-flag-in-localStorage pattern as `shortcutsEnabled` in
 * KeyboardLayer.tsx: set once on Skip or Finish, never re-shown after. */
export function hasSeenTour(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(SEEN_KEY) === "true";
}

export function markTourSeen(): void {
  window.localStorage.setItem(SEEN_KEY, "true");
}

/** "Replay tour" in the shortcut sheet asks for this; TourOverlay listens
 * for it the same way CommandMenu listens for proofline:open-command-menu. */
export function requestTourStart(): void {
  window.dispatchEvent(new Event(START_TOUR_EVENT));
}

export type TourRole = "preparer" | "other";

export function tourRoleFor(role: string | undefined): TourRole {
  return role === "preparer" ? "preparer" : "other";
}

export type TourStep = {
  key: string;
  title: string;
  body: string;
};

const SHARED_STEPS: TourStep[] = [
  {
    key: "status",
    title: "Every case has a status",
    body:
      "From Open to Resolved. The queue groups cases by severity, so what blocks filing surfaces first.",
  },
  {
    key: "evidence",
    title: "Trace it",
    body:
      "Evidence is never just the client's word. Click a card to open the exact source document, with the field highlighted -- that's how a number traces back to its proof.",
  },
];

const PREPARER_LAST_STEP: TourStep = {
  key: "proposal",
  title: "Submit a proposal",
  body:
    "When you've worked out what happened, submit a proposal here -- pick the resolution type and attach your evidence. A reviewer decides next; nobody reviews their own work.",
};

const REVIEWER_LAST_STEP: TourStep = {
  key: "decision",
  title: "The decision bar",
  body:
    "This is where you decide: Approve, Return it for more work, or -- over $1,000 tax effect -- send it to the partner. Only the actions you're allowed to take right now are enabled; the rest explain why.",
};

export function tourSteps(role: TourRole): TourStep[] {
  const lastStep = role === "preparer" ? PREPARER_LAST_STEP : REVIEWER_LAST_STEP;
  return [...SHARED_STEPS, lastStep];
}

/** Finds a real case to open for steps 2-3, matching the status each
 * track needs (CLAUDE.md: never hard-code a packet value or expected
 * answer -- this picks from whatever the live queue actually has).
 * shortcut: no fallback case means steps 2-3 are skipped if the queue
 * has none in the right status; upgrade only if that's ever reported
 * as confusing in practice. */
export async function pickTourCase(role: TourRole): Promise<CaseRow | null> {
  const wantedStatus = role === "preparer" ? "investigating" : "in_review";
  try {
    const queue = await apiFetch<QueueResponse>("/api/cases?tab=all_open");
    for (const group of queue.groups) {
      const match = group.cases.find((row) => row.status === wantedStatus);
      if (match) return match;
    }
  } catch {
    // Same "don't swallow silently, but don't crash the tour either"
    // tradeoff the queue sync button already makes.
  }
  return null;
}
