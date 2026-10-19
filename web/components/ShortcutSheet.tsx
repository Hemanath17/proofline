"use client";

import styles from "./ShortcutSheet.module.css";

const SHORTCUTS: Array<[string, string]> = [
  ["J / K", "Next or previous item"],
  ["Enter", "Open"],
  ["Esc", "Close or back"],
  ["X", "Select"],
  ["/", "Filter"],
  ["G Q", "Go to queue"],
  ["G A", "Go to areas"],
  ["G D", "Go to documents"],
  ["T", "Trace the focused number"],
  ["V", "Mark verified"],
  ["N", "Add review note"],
  ["?", "This shortcut sheet"],
  ["Cmd/Ctrl+K", "Command menu"],
];

export function ShortcutSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className={styles.title}>Keyboard shortcuts</h2>
        <dl className={styles.list}>
          {SHORTCUTS.map(([key, description]) => (
            <div key={key} className={styles.row}>
              <dt className={`mono ${styles.key}`}>{key}</dt>
              <dd>{description}</dd>
            </div>
          ))}
        </dl>
        <button type="button" className={styles.close} onClick={onClose} autoFocus>
          Close
        </button>
      </div>
    </div>
  );
}
