"use client";

import styles from "./Shared.module.css";

/** A generic, read-only renderer for the sixteen CPA record views
 * (R01-R16): rather than sixteen bespoke table layouts, one recursive
 * renderer that shows an array of objects as a table, an object as a
 * labelled list, and anything else as plain text -- "detail tables are
 * read-only views", not a spreadsheet (docs/UX.md principle 6). */
export function JsonValue({ value }: { value: unknown }): React.ReactElement {
  if (value === null || value === undefined) {
    return <span className="mono">—</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className={styles.emptyState}>none</span>;
    const allObjects = value.every((item) => typeof item === "object" && item !== null && !Array.isArray(item));
    if (allObjects) {
      const columns = Array.from(new Set(value.flatMap((row) => Object.keys(row as object))));
      return (
        <table className={styles.table}>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column} className="mono">
                    <JsonValue value={(row as Record<string, unknown>)[column]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    return <span className="mono">{value.map((item) => String(item)).join(", ")}</span>;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return (
      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
        {entries.map(([key, item]) => (
          <div key={key} style={{ display: "contents" }}>
            <dt className={styles.small}>{key}</dt>
            <dd>
              <JsonValue value={item} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  if (typeof value === "boolean") return <span className="mono">{value ? "true" : "false"}</span>;
  return <span className="mono">{String(value)}</span>;
}
