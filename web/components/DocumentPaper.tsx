"use client";

import type { Highlight } from "@/lib/types";
import styles from "./DocumentPaper.module.css";

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
        <pre className={`mono ${styles.content}`}>{printedContent}</pre>
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
