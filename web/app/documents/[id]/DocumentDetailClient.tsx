"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { DocumentPaper } from "@/components/DocumentPaper";
import type { DocumentDetail, DocumentPage } from "@/lib/types";
import styles from "./page.module.css";

function DispositionPill({ disposition }: { disposition: string | null }) {
  const label = disposition ?? "pending";
  return <span className={styles.dispositionPill}>{label.replaceAll("_", " ")}</span>;
}

export function DocumentDetailClient({ documentId }: { documentId: string }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [pages, setPages] = useState<Record<number, DocumentPage>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<DocumentDetail>(`/api/documents/${documentId}`)
      .then((body) => {
        if (cancelled) return;
        setDetail(body);
        return Promise.all(
          body.pages.map((page) =>
            apiFetch<DocumentPage>(`/api/documents/${documentId}/pages/${page}`),
          ),
        );
      })
      .then((loadedPages) => {
        if (cancelled || !loadedPages) return;
        const byPage: Record<number, DocumentPage> = {};
        loadedPages.forEach((page) => {
          byPage[page.page] = page;
        });
        setPages(byPage);
      })
      .catch(() => {
        if (!cancelled) setError("couldn't load this document");
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!detail) return <p className={styles.loading}>Loading...</p>;

  return (
    <div>
      <Link href="/documents" className={styles.backLink}>
        ← Back to documents
      </Link>
      <header className={styles.header}>
        <h1>{detail.title}</h1>
        <div className={styles.metaRow}>
          <span>{detail.document_type}</span>
          {detail.issuer && <span>{detail.issuer}</span>}
          <DispositionPill disposition={detail.disposition} />
        </div>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Landed in</h2>
        {detail.used ? (
          <ul className={styles.linkList}>
            {detail.lines_using.map((lineKey) => (
              <li key={lineKey}>
                <Link href={`/trace/line/${lineKey}`} className={`mono ${styles.lineLink}`}>
                  {lineKey}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.small}>{detail.note ?? "This document isn't used by any line."}</p>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Pages</h2>
        <div className={styles.pageStack}>
          {detail.pages.map((pageNumber) => (
            <DocumentPaper
              key={pageNumber}
              pageNumber={pageNumber}
              printedContent={pages[pageNumber]?.printed_content ?? "Loading..."}
              highlights={[]}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
