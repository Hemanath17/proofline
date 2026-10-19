"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import styles from "./list.module.css";

type DocumentSummary = {
  id: string;
  title: string;
  document_type: string;
  issuer: string | null;
  tax_year: number | null;
  received_at: string | null;
  page_count: number;
  marked_corrected: boolean | null;
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ documents: DocumentSummary[] }>("/api/documents").then((body) => {
      if (!cancelled) setDocuments(body.documents);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1>Documents</h1>
      {!documents && <p style={{ color: "var(--ink-2)", marginTop: 8 }}>Loading...</p>}
      <ul className={styles.list}>
        {documents?.map((document) => (
          <li key={document.id}>
            <Link href={`/documents/${document.id}`} className={styles.row}>
              <span className={`mono ${styles.id}`}>{document.id}</span>
              <span className={styles.title}>{document.title}</span>
              <span className={styles.type}>{document.document_type}</span>
              {document.marked_corrected && <span className={styles.correctedBadge}>Corrected</span>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
