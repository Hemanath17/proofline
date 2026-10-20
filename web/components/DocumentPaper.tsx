"use client";

import type { Highlight } from "@/lib/types";
import styles from "./DocumentPaper.module.css";

function LockIcon() {
  return (
    <svg
      className={styles.lockIcon}
      viewBox="0 0 16 16"
      width="10"
      height="10"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <rect x="3" y="7" width="10" height="7" rx="1.5" />
      <path d="M5.5 7V4.5a2.5 2.5 0 0 1 5 0V7" />
    </svg>
  );
}

// The API masks a sensitive value in place (docs/UX.md Sensitive values:
// "***-**-3390", "****4471") rather than sending a separate flag, so the
// only way to find one here is the same shape: two or more asterisks,
// optionally with dashes, ending in the kept last few digits.
const MASKED_VALUE = /\*{2,}[-*]*\d{2,4}/g;

/** Splits printed_content on masked spans so each one can get the "this is
 * intentionally withheld" treatment (lock icon, title) instead of reading
 * as plain or broken text. */
function renderContent(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  MASKED_VALUE.lastIndex = 0;
  while ((match = MASKED_VALUE.exec(text))) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(
      <span key={key++} className={styles.masked} title="Masked -- withheld for this role">
        <LockIcon />
        {match[0]}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

/** Renders one document page as a paper sheet (docs/UX.md Visual system:
 * "white page, subtle shadow, monospace printed_content, page number in
 * the margin"). Highlights are translucent boxes positioned from the
 * extracted value's normalised (0-1) `position`, each with a small
 * numbered tag. */
export function DocumentPaper({
  pageNumber,
  printedContent,
  highlights,
}: {
  pageNumber: number;
  printedContent: string;
  highlights: Highlight[];
}) {
  return (
    <div className={styles.wrap}>
      <div className={styles.margin}>Page {pageNumber}</div>
      <div className={styles.sheet}>
        <pre className={`mono ${styles.content}`}>{renderContent(printedContent)}</pre>
        {highlights.map((highlight) =>
          highlight.position ? (
            <span
              key={highlight.ev_id}
              className={styles.highlight}
              style={{
                left: `${highlight.position.x0 * 100}%`,
                top: `${highlight.position.y0 * 100}%`,
                width: `${(highlight.position.x1 - highlight.position.x0) * 100}%`,
                height: `${(highlight.position.y1 - highlight.position.y0) * 100}%`,
              }}
              title={highlight.label ?? highlight.field}
            >
              <span className={styles.tag}>{highlight.tag}</span>
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}
