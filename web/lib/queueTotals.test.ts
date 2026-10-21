import { describe, expect, it } from "vitest";
import { sumTaxEffectFederal } from "@/lib/queueTotals";
import type { CaseRow } from "@/lib/types";

function row(federal: string | null): CaseRow {
  return {
    case_id: `case-${federal}`,
    root_cause_key: "x",
    origin: "check",
    origin_ref: null,
    scope: "wages",
    claims: [],
    severity: "tax_amount",
    finding_type: null,
    priority: 1,
    assignee_id: null,
    status: "investigating",
    revision: 1,
    check_id: null,
    check_version: null,
    evidence_refs: [],
    observed: null,
    expected: null,
    limitations: null,
    recommended_action: null,
    tax_effect: federal === null ? null : { federal, california: "0", kind: "estimate", direction: "overstated" },
    impact_unknown: federal === null,
    cleared_reason: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    changed_since_last_seen: false,
    change_summary: null,
    why_it_here: null,
    title: null,
    proposal_count: 0,
  };
}

describe("sumTaxEffectFederal", () => {
  it("sums the federal tax effect across rows", () => {
    expect(sumTaxEffectFederal([row("1000"), row("2500")])).toBe(3500);
  });

  it("treats a row with no tax effect as zero, same as the server's own total", () => {
    expect(sumTaxEffectFederal([row("1000"), row(null)])).toBe(1000);
  });

  it("matches the server total when given the whole unfiltered group, and only the subset's sum when filtered", () => {
    const wholeGroup = [row("1000"), row("2000"), row("3000")];
    expect(sumTaxEffectFederal(wholeGroup)).toBe(6000);

    const filtered = wholeGroup.slice(0, 1);
    expect(sumTaxEffectFederal(filtered)).toBe(1000);
  });

  it("is zero for an empty list", () => {
    expect(sumTaxEffectFederal([])).toBe(0);
  });
});
