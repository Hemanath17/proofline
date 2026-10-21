import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { EvidenceContent } from "@/components/EvidenceContent";
import { apiFetch } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
}));

const mockedApiFetch = apiFetch as unknown as ReturnType<typeof vi.fn>;

describe("EvidenceContent", () => {
  it("renders a document-field preview with the document paper and a highlight", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/api/trace/evidence")) {
        return Promise.resolve({
          kind: "document_field",
          ref: "ev-0001",
          document_id: "D01",
          document_title: "Form 1040",
          page: 2,
          field: "signed_date_taxpayer",
          label: "Signed date",
          value: "2026-04-01",
          text_as_read: "04/01/2026",
          position: { x0: 0.1, y0: 0.1, x1: 0.3, y1: 0.2 },
        });
      }
      return Promise.resolve({ document_id: "D01", page: 2, printed_content: "printed page text" });
    });

    render(<EvidenceContent reference="ev-0001" />);

    expect(await screen.findByText("Form 1040")).toBeInTheDocument();
    expect(await screen.findByText("printed page text")).toBeInTheDocument();
    expect(screen.getByText("Open full document trace")).toHaveAttribute("href", "/documents/D01");
  });

  it("renders a client-statement preview with the 'not verification' warning", async () => {
    mockedApiFetch.mockResolvedValue({
      kind: "message",
      ref: "msg-01",
      from: "client",
      to: "preparer",
      sent_at: "2026-02-01T00:00:00Z",
      text: "Here's the missing W-2.",
    });

    render(<EvidenceContent reference="msg-01" />);

    expect(await screen.findByText(/client statement, not verification/)).toBeInTheDocument();
    expect(screen.getByText("Here's the missing W-2.")).toBeInTheDocument();
  });

  it("renders a typed card for a non-document, non-client reference", async () => {
    mockedApiFetch.mockResolvedValue({
      kind: "typed",
      ref: "household:ngozi",
      label: "Household fact",
      value: { id: "ngozi", name: "Ngozi" },
    });

    render(<EvidenceContent reference="household:ngozi" />);

    expect(await screen.findByText("Household fact")).toBeInTheDocument();
  });

  it("shows an error state when the preview fails to load", async () => {
    mockedApiFetch.mockRejectedValue(new Error("boom"));

    render(<EvidenceContent reference="not-a-real-ref" />);

    await waitFor(() => expect(screen.getByText(/couldn't load this evidence/)).toBeInTheDocument());
  });
});
