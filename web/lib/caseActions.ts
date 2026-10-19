/** Mirrors proofline/security/permissions.py's C1 rules so the decision
 * bar can show a disabled action with its reason (docs/UX.md: "A disabled
 * action stays on screen with its reason"). This is display only -- the
 * API enforces every rule for real; the UI never grants anything this
 * helper happens to get wrong (CLAUDE.md: "Rely on the UI for permissions"
 * is exactly what this is not doing). */

import type { ActorSummary } from "@/lib/session";
import type { CaseDetail } from "@/lib/types";

export type CaseAction =
  | "pick_up"
  | "ask_client"
  | "client_answered"
  | "submit_proposal"
  | "return"
  | "approve"
  | "partner_approve"
  | "partner_return"
  | "reopen"
  | "reassign";

export type ActionAvailability = {
  action: CaseAction;
  label: string;
  nextStatusHint?: string;
  enabled: boolean;
  reason?: string;
};

const REVIEWER_ROLES = new Set(["reviewer", "partner", "quality_reviewer"]);

export function availableActions(
  actor: ActorSummary | undefined,
  caseDetail: CaseDetail,
): ActionAvailability[] {
  const role = actor?.role;
  const latestProposal = caseDetail.proposals[caseDetail.proposals.length - 1];
  const ownWork = Boolean(latestProposal && actor && latestProposal.proposed_by === actor.id);
  const overThreshold =
    caseDetail.tax_effect != null &&
    (Math.abs(Number(caseDetail.tax_effect.federal)) > 1000 ||
      Math.abs(Number(caseDetail.tax_effect.california)) > 1000);

  const actions: ActionAvailability[] = [];

  if (caseDetail.status === "open") {
    actions.push({
      action: "pick_up",
      label: "Pick up",
      enabled: role === "preparer",
      reason: role === "preparer" ? undefined : "preparer only",
    });
  }

  if (caseDetail.status === "investigating") {
    actions.push({
      action: "ask_client",
      label: "Ask client",
      enabled: role === "preparer",
      reason: role === "preparer" ? undefined : "preparer only",
    });
    actions.push({
      action: "submit_proposal",
      label: "Submit proposal",
      enabled: role === "preparer",
      reason: role === "preparer" ? undefined : "preparer only",
    });
  }

  if (caseDetail.status === "waiting_on_client") {
    actions.push({
      action: "client_answered",
      label: "Record client answer",
      enabled: role === "client" || role === "system",
      reason: role === "client" || role === "system" ? undefined : "client or system only",
    });
  }

  if (caseDetail.status === "in_review") {
    actions.push({
      action: "return",
      label: "Return",
      enabled: Boolean(role && REVIEWER_ROLES.has(role) && !ownWork),
      reason:
        role && REVIEWER_ROLES.has(role)
          ? ownWork
            ? "you proposed this. Nobody reviews their own work."
            : undefined
          : "only a reviewer, partner or quality reviewer may decide on a proposal",
    });
    actions.push({
      action: "approve",
      label: "Approve",
      nextStatusHint: overThreshold
        ? "→ Awaiting partner: tax effect over 1,000"
        : "→ Resolved",
      enabled: Boolean(role && REVIEWER_ROLES.has(role) && !ownWork),
      reason:
        role && REVIEWER_ROLES.has(role)
          ? ownWork
            ? "you proposed this. Nobody reviews their own work."
            : undefined
          : "only a reviewer, partner or quality reviewer may decide on a proposal",
    });
  }

  if (caseDetail.status === "awaiting_partner") {
    actions.push({
      action: "partner_approve",
      label: "Partner approve",
      nextStatusHint: "→ Resolved",
      enabled: role === "partner",
      reason: role === "partner" ? undefined : "partner only",
    });
    actions.push({
      action: "partner_return",
      label: "Partner return",
      enabled: role === "partner",
      reason: role === "partner" ? undefined : "partner only",
    });
  }

  if (caseDetail.status === "resolved") {
    actions.push({
      action: "reopen",
      label: "Reopen",
      enabled: Boolean(role && (role === "system" || REVIEWER_ROLES.has(role))),
      reason:
        role && (role === "system" || REVIEWER_ROLES.has(role))
          ? undefined
          : "only the system or a reviewer may reopen a case",
    });
  }

  if (!["resolved", "cleared"].includes(caseDetail.status)) {
    actions.push({
      action: "reassign",
      label: "Reassign",
      enabled: role === "preparer" || role === "reviewer" || role === "firm_administrator",
      reason:
        role === "preparer" || role === "reviewer" || role === "firm_administrator"
          ? undefined
          : "only a preparer, reviewer or admin may reassign a case",
    });
  }

  return actions;
}
