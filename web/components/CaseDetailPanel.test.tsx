import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CaseDetailPanel } from "@/components/CaseDetailPanel";
import { apiFetch, apiPost, ApiError } from "@/lib/api-client";
import { useCurrentActor } from "@/lib/session";
import type { CaseDetail } from "@/lib/types";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
  apiPost: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    body: unknown;
    constructor(status: number, detail: string, body: unknown) {
      super(detail);
      this.status = status;
      this.detail = detail;
      this.body = body;
    }
  },
}));

vi.mock("@/lib/session", () => ({
  useCurrentActor: vi.fn(),
}));

const mockedApiFetch = apiFetch as unknown as ReturnType<typeof vi.fn>;
const mockedApiPost = apiPost as unknown as ReturnType<typeof vi.fn>;
const mockedUseCurrentActor = useCurrentActor as unknown as ReturnType<typeof vi.fn>;

function investigatingCase(evidenceRefs: string[]): CaseDetail {
  return {
    case_id: "case-1",
    root_cause_key: "x",
    origin: "check",
    origin_ref: null,
    scope: "wages",
    claims: [],
    severity: "tax_amount",
    finding_type: null,
    priority: 1,
    assignee_id: "st-01",
    status: "investigating",
    revision: 3,
    check_id: "SOME_CHECK",
    check_version: 1,
    evidence_refs: evidenceRefs,
    observed: "observed text",
    expected: "expected text",
    limitations: null,
    recommended_action: null,
    tax_effect: null,
    impact_unknown: true,
    cleared_reason: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    changed_since_last_seen: false,
    change_summary: null,
    why_it_here: "why it matters",
    title: "A test case",
    proposal_count: 0,
    proposals: [],
    decisions: [],
  };
}

beforeEach(() => {
  mockedApiFetch.mockReset();
  mockedApiPost.mockReset();
  mockedUseCurrentActor.mockReset();
  mockedUseCurrentActor.mockReturnValue({
    actor: { id: "st-01", name: "Priya", role: "preparer", clearance: true },
    actors: [],
    actorId: "st-01",
    setActorId: vi.fn(),
  });
});

describe("CaseDetailPanel error state", () => {
  it("shows a Retry button on load failure, which re-fetches", async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(500, "server exploded", null));

    render(<CaseDetailPanel caseId="case-1" />);

    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(screen.getByText("server exploded")).toBeInTheDocument();

    mockedApiFetch.mockResolvedValueOnce(investigatingCase([]));
    mockedApiFetch.mockResolvedValueOnce({ events: [] });
    fireEvent.click(retry);

    await waitFor(() => expect(screen.getByText("A test case")).toBeInTheDocument());
  });
});

describe("CaseDetailPanel proposal evidence picker", () => {
  it("submits the exact same evidence_refs: string[] shape submit_proposal expects", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.endsWith("/activity")) return Promise.resolve({ events: [] });
      return Promise.resolve(investigatingCase(["ev-0001", "msg-01"]));
    });
    mockedApiPost.mockResolvedValue({});

    render(<CaseDetailPanel caseId="case-1" />);

    await screen.findByText("A test case");

    // The proposal's evidence field is a checkbox picker over the case's
    // own evidence_refs, not a free-text input.
    expect(screen.queryByRole("textbox", { name: /evidence/i })).toBeNull();

    fireEvent.click(screen.getByRole("checkbox", { name: /ev-0001/ }));

    const reasonInput = screen.getByLabelText("Reason the difference is expected");
    fireEvent.change(reasonInput, { target: { value: "explained by the client" } });

    fireEvent.click(screen.getByRole("button", { name: "Submit proposal" }));

    await waitFor(() => expect(mockedApiPost).toHaveBeenCalled());
    const [path, body] = mockedApiPost.mock.calls[0];
    expect(path).toBe("/api/cases/case-1/submit-proposal");
    expect(body.evidence_refs).toEqual(["ev-0001"]);
    expect(Array.isArray(body.evidence_refs)).toBe(true);
  });
});
