"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCurrentActor } from "@/lib/session";
import {
  START_TOUR_EVENT,
  hasSeenTour,
  markTourSeen,
  pickTourCase,
  tourRoleFor,
  tourSteps,
} from "@/lib/tour";
import styles from "./TourOverlay.module.css";

const STATUS_LABELS = new Set([
  "Open",
  "Investigating",
  "Waiting on client",
  "In review",
  "Awaiting partner",
  "Resolved",
  "Cleared",
]);

/** Finds this step's target element from outside Queue/CaseDetailPanel --
 * no data-tour-* attributes added to those files, only selectors built
 * from markup that's already stable and meaningful (docs/UX.md labels,
 * the one <footer> CaseDetailPanel renders, the literal button text). */
function findStepTarget(stepIndex: number): HTMLElement | null {
  if (stepIndex === 0) {
    return (
      Array.from(document.querySelectorAll<HTMLElement>("span")).find(
        (el) => el.children.length === 0 && STATUS_LABELS.has(el.textContent?.trim() ?? ""),
      ) ?? null
    );
  }
  if (stepIndex === 1) {
    const heading = Array.from(document.querySelectorAll("h3")).find(
      (el) => el.textContent?.trim() === "Evidence",
    );
    const section = heading?.closest("section");
    return section?.querySelector<HTMLElement>("li button") ?? null;
  }
  const submitButton = Array.from(document.querySelectorAll<HTMLElement>("button")).find(
    (el) => el.textContent?.trim() === "Submit proposal",
  );
  if (submitButton) return submitButton;
  const proposalHeading = Array.from(document.querySelectorAll("h3")).find(
    (el) => el.textContent?.trim() === "Proposal",
  );
  const proposalSection = proposalHeading?.closest("section") ?? null;
  if (proposalSection) return proposalSection;
  return document.querySelector<HTMLElement>("footer");
}

/** Polls for a step's target rather than depending on a mutation callback
 * from code this component doesn't own -- simple, and the tour is a rare,
 * low-frequency UI, not a perf-sensitive path. Gives up after ~4s. */
function useStepTarget(stepIndex: number, active: boolean): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!active) {
      setRect(null);
      return;
    }
    let attempts = 0;
    let cancelled = false;

    function measure() {
      const el = findStepTarget(stepIndex);
      if (el) {
        setRect(el.getBoundingClientRect());
        return true;
      }
      return false;
    }

    if (!measure()) {
      const interval = setInterval(() => {
        attempts += 1;
        if (cancelled) return;
        if (measure() || attempts > 40) clearInterval(interval);
      }, 100);
      return () => {
        cancelled = true;
        clearInterval(interval);
      };
    }

    function reposition() {
      const el = findStepTarget(stepIndex);
      if (el) setRect(el.getBoundingClientRect());
    }
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [stepIndex, active]);

  return rect;
}

/** The spotlight tour over the real Queue and Case Detail screens
 * (docs/UX.md S1/S2). Shows once per browser on first load of /queue,
 * and is permanently replayable from the "?" shortcut sheet. Has no
 * keyboard bindings of its own, so J/K/Enter/Esc keep working under it. */
export function TourOverlay() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { actor } = useCurrentActor();

  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [pendingStart, setPendingStart] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const autoStartChecked = useRef(false);

  const role = tourRoleFor(actor?.role);
  const steps = tourSteps(role);
  const rect = useStepTarget(step, active);

  const finish = useCallback(() => {
    markTourSeen();
    setActive(false);
    setStep(0);
  }, []);

  useEffect(() => {
    if (autoStartChecked.current) return;
    if (pathname !== "/queue") return;
    autoStartChecked.current = true;
    if (!hasSeenTour()) setActive(true);
  }, [pathname]);

  useEffect(() => {
    function onStartRequest() {
      setStep(0);
      if (pathname === "/queue") {
        setActive(true);
      } else {
        setPendingStart(true);
        router.push("/queue");
      }
    }
    window.addEventListener(START_TOUR_EVENT, onStartRequest);
    return () => window.removeEventListener(START_TOUR_EVENT, onStartRequest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    if (pendingStart && pathname === "/queue") {
      setPendingStart(false);
      setActive(true);
    }
  }, [pendingStart, pathname]);

  async function next() {
    if (step === 0) {
      setAdvancing(true);
      const tourCase = await pickTourCase(role);
      setAdvancing(false);
      if (!tourCase) {
        finish();
        return;
      }
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", "all_open");
      params.set("case", tourCase.case_id);
      router.push(`/queue?${params.toString()}`);
      setStep(1);
      return;
    }
    if (step === steps.length - 1) {
      finish();
      return;
    }
    setStep((value) => value + 1);
  }

  if (!active || pathname !== "/queue") return null;

  const current = steps[step];
  const isLast = step === steps.length - 1;

  return (
    <div className={styles.overlay} role="presentation">
      {rect && (
        <div
          className={styles.ring}
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <div
        className={styles.tooltip}
        style={
          rect
            ? {
                // 260px covers this tooltip's tallest body copy plus the
                // step count and action row -- keeps Next/Skip on-screen
                // even when the target sits low on the page.
                top: Math.min(rect.bottom + 12, window.innerHeight - 260),
                left: Math.min(Math.max(rect.left, 16), window.innerWidth - 316),
              }
            : { top: "40%", left: "50%", transform: "translate(-50%, -50%)" }
        }
        role="dialog"
        aria-modal="false"
        aria-label={`Tour step ${step + 1} of ${steps.length}: ${current.title}`}
      >
        <p className={styles.stepCount}>
          Step {step + 1} of {steps.length}
        </p>
        <h3 className={styles.title}>{current.title}</h3>
        <p className={styles.body}>{current.body}</p>
        <div className={styles.actions}>
          <button type="button" className={styles.skip} onClick={finish}>
            Skip
          </button>
          <button type="button" className={styles.next} onClick={next} disabled={advancing}>
            {advancing ? "Finding a case..." : isLast ? "Finish" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
