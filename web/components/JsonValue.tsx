"use client";

import styles from "./Shared.module.css";

/** A generic, read-only renderer for the sixteen CPA record views
 * (R01-R16): rather than sixteen bespoke table layouts, one recursive
 * renderer that shows an array of objects as a table, an object as a
 * labelled list, and anything else as plain text -- "detail tables are
 * read-only views", not a spreadsheet (docs/UX.md principle 6). */
// Record values come straight from the API as JSON numbers in some views
// and as Decimal-precision strings in others (e.g. a percent_change like
// "36.11981619979620479495510738") -- round here, for display only,
// rather than showing 20+ raw decimal digits.
function formatNumber(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString("en-US");
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

// Same rule the rest of the app's formatValue helpers already use for a
// line amount (AreaDetail, the Return page): a numeric-looking value gets
// comma-formatted. shortcut: a bare numeric code (zip, account number)
// would get comma-formatted too; none of R01-R16's current fields are
// that shape.
const NUMERIC_STRING = /^-?\d+(\.\d+)?$/;

function isFormattableNumericString(value: string): boolean {
  return NUMERIC_STRING.test(value);
}

export function JsonValue({ value }: { value: unknown }): React.ReactElement {
  if (value === null || value === undefined) {
    return <span className="mono">—</span>;
  }
  if (typeof value === "number") {
    return <span className="mono">{formatNumber(value)}</span>;
  }
  if (typeof value === "string" && isFormattableNumericString(value)) {
    return <span className="mono">{formatNumber(Number(value))}</span>;
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
                {columns.map((column) => {
                  const cell = (row as Record<string, unknown>)[column];
                  const numeric =
                    typeof cell === "number" || (typeof cell === "string" && isFormattableNumericString(cell));
                  return (
                    <td key={column} className={`mono ${numeric ? styles.num : ""}`}>
                      <JsonValue value={cell} />
                    </td>
                  );
                })}
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
