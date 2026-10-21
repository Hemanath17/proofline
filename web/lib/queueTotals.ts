import type { CaseRow } from "@/lib/types";

/** The federal tax-effect total for a set of rows, summed client-side so
 * it always matches what's actually visible -- including when the queue's
 * search filter has narrowed `rows` to a subset of a group. Mirrors the
 * server's own `_tax_effect_total` (`routes/cases.py`: `sum(c.tax_effect_federal
 * or 0 for c in cases)`), so this gives the identical number when `rows`
 * is a whole, unfiltered group. */
export function sumTaxEffectFederal(rows: CaseRow[]): number {
  return rows.reduce((sum, row) => sum + Number(row.tax_effect?.federal ?? 0), 0);
}
