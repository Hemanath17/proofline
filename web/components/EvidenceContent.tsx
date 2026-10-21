"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import type { DocumentPage, EvidencePreview, Highlight } from "@/lib/types";
import { DocumentPaper } from "@/components/DocumentPaper";
import styles from "./EvidenceContent.module.css";

/** Renders one evidence reference's preview (docs/UX.md S2 "Evidence: one
 * card per evidence reference... a click opens the Trace drawer"), fed by
 * `GET /api/trace/evidence?ref=`. Document-backed refs reuse the existing
 * `DocumentPaper` paper-sheet rendering and the existing document-page
 * route -- the same source view S4's Trace content uses, not a second
 * one. */
export function EvidenceContent({ reference }: { reference: string }) {
  const [preview, setPreview] = useState<EvidencePreview | null>(null);
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPreview(null);
    setPage(null);
    setError(null);
    apiFetch<EvidencePreview>(`/api/trace/evidence?ref=${encodeURIComponent(reference)}`)
      .then((body) => {
        if (!cancelled) setPreview(body);
      })
      .catch(() => {
        if (!cancelled) setError("couldn't load this evidence");
      });
    return () => {
      cancelled = true;
    };
  }, [reference]);

  useEffect(() => {
    if (!preview) return;
    if (preview.kind !== "document_field" && preview.kind !== "document_page") return;
    if (!preview.document_id) return;
    let cancelled = false;
    apiFetch<DocumentPage>(`/api/documents/${preview.document_id}/pages/${preview.page}`)
      .then((body) => {
        if (!cancelled) setPage(body);
      });
    return () => {
      cancelled = true;
    };
  }, [preview]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!preview) return <p className={styles.loading}>Loading...</p>;

  if (preview.kind === "document_field" || preview.kind === "document_page") {
    if (!preview.document_id) return <p className={styles.loading}>No document for this reference.</p>;
    const highlights: Highlight[] =
      preview.kind === "document_field" && preview.position
        ? [
            {
              ev_id: preview.ref,
              field: preview.field,
              label: preview.label,
              tag: 1,
              position: preview.position,
            },
          ]
        : [];
    return (
      <div className={styles.layout}>
        <p className={styles.sourceLabel}>{preview.document_title ?? preview.document_id}</p>
        {page ? (
          <DocumentPaper pageNumber={preview.page} printedContent={page.printed_content} highlights={highlights} />
        ) : (
          <p className={styles.loading}>Loading page...</p>
        )}
        <a className={styles.link} href={`/documents/${preview.document_id}`}>
          Open full document trace
        </a>
      </div>
    );
  }

  if (preview.kind === "document") {
    return (
      <div className={styles.card}>
        <p className={styles.cardKind}>Document</p>
        <p className={styles.cardTitle}>{preview.title}</p>
        <p className={styles.small}>
          {preview.document_type}
          {preview.issuer ? ` · ${preview.issuer}` : ""}
        </p>
        <a className={styles.link} href={`/documents/${preview.document_id}`}>
          Open full document trace
        </a>
      </div>
    );
  }

  if (
    preview.kind === "questionnaire_item" ||
    preview.kind === "message" ||
    preview.kind === "call_note"
  ) {
    return (
      <div className={styles.card}>
        <p className={styles.clientNote}>Client said · client statement, not verification</p>
        {preview.kind === "questionnaire_item" && (
          <>
            <p className={styles.small}>{preview.question}</p>
            <p>{String(preview.answer)}</p>
          </>
        )}
        {preview.kind === "message" && <p>{preview.text}</p>}
        {preview.kind === "call_note" && (
          <ul className={styles.notesList}>
            {preview.notes.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <p className={styles.cardKind}>{preview.label}</p>
      <pre className={`mono ${styles.typedValue}`}>{JSON.stringify(preview.value, null, 2)}</pre>
    </div>
  );
}
