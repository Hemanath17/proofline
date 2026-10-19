"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import type { DocumentPage, LineTraceResponse, TraceSource } from "@/lib/types";
import { DocumentPaper } from "@/components/DocumentPaper";
import { ProvenanceBadge } from "@/components/Badges";
import styles from "./TraceContent.module.css";

function TracePage({ documentId, source }: { documentId: string; source: TraceSource }) {
  const [pages, setPages] = useState<Record<number, DocumentPage>>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      source.pages.map((page) =>
        apiFetch<DocumentPage>(`/api/documents/${documentId}/pages/${page.page}`),
      ),
    ).then((loaded) => {
      if (cancelled) return;
      const byPage: Record<number, DocumentPage> = {};
      loaded.forEach((page) => {
        byPage[page.page] = page;
      });
      setPages(byPage);
    });
    return () => {
      cancelled = true;
    };
  }, [documentId, source]);

  return (
    <div className={styles.pageStack}>
      {source.pages.map((page) => (
        <DocumentPaper
          key={page.page}
          pageNumber={page.page}
          printedContent={pages[page.page]?.printed_content ?? "Loading..."}
          highlights={page.highlights}
        />
      ))}
    </div>
  );
}

export function TraceContent({
  lineKey,
  onNavigate,
}: {
  lineKey: string;
  onNavigate: (lineKey: string) => void;
}) {
  const [trace, setTrace] = useState<LineTraceResponse | null>(null);
  const [activeDocument, setActiveDocument] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setTrace(null);
    setError(null);
    apiFetch<LineTraceResponse>(`/api/trace/line/${lineKey}`)
      .then((body) => {
        if (cancelled) return;
        setTrace(body);
        setActiveDocument(body.sources[0]?.document_id ?? null);
      })
      .catch(() => {
        if (!cancelled) setError("couldn't load this line's trace");
      });
    return () => {
      cancelled = true;
    };
  }, [lineKey]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!trace) return <p className={styles.loading}>Loading...</p>;

  const activeSource = trace.sources.find((s) => s.document_id === activeDocument);

  return (
    <div className={styles.layout}>
      <div className={styles.numberCard}>
        <h3 className={`mono ${styles.lineKey}`}>{trace.line_key}</h3>
        <p className={styles.label}>{trace.label}</p>
        <p className={styles.valueRow}>
          <span className={`mono ${styles.value}`}>{String(trace.value)}</span>
          <ProvenanceBadge kind={trace.provenance} />
        </p>
        {trace.adjustment && (
          <p className={styles.adjustmentNote}>
            Adjusted from <span className="mono">{trace.adjustment.old_value}</span> to{" "}
            <span className="mono">{trace.adjustment.new_value}</span>
          </p>
        )}
        <p className={styles.rule}>
          Rule: <span className="mono">{trace.rule}</span>
        </p>

        {trace.inputs.length > 0 && (
          <section className={styles.section}>
            <h4 className={styles.sectionTitle}>Inputs</h4>
            <ul className={styles.linkList}>
              {trace.inputs.map((key) => (
                <li key={key}>
                  <button type="button" className={styles.linkButton} onClick={() => onNavigate(key)}>
                    {key}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {trace.used_by.length > 0 && (
          <section className={styles.section}>
            <h4 className={styles.sectionTitle}>Used by</h4>
            <ul className={styles.linkList}>
              {trace.used_by.map((key) => (
                <li key={key}>
                  <button type="button" className={styles.linkButton} onClick={() => onNavigate(key)}>
                    {key}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {trace.other_sources.length > 0 && (
          <section className={styles.section}>
            <h4 className={styles.sectionTitle}>Other sources</h4>
            <ul className={styles.cardList}>
              {trace.other_sources.map((other) => (
                <li key={other.ref} className={styles.card}>
                  <span className="mono">{other.ref}</span>
                  <span className={styles.cardKind}>{other.kind.replaceAll("_", " ")}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {trace.excluded.length > 0 && (
          <section className={styles.section}>
            <h4 className={styles.sectionTitle}>Not used here</h4>
            <ul className={styles.cardList}>
              {trace.excluded.map((excluded) => (
                <li key={excluded.document_id} className={styles.card}>
                  <span className="mono">{excluded.document_id}</span>
                  <span className={styles.cardKind}>{excluded.reason}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <div className={styles.sourcePane}>
        {trace.sources.length > 1 && (
          <div className={styles.tabs}>
            {trace.sources.map((source) => (
              <button
                key={source.document_id}
                type="button"
                className={`${styles.tab} ${activeDocument === source.document_id ? styles.tabActive : ""}`}
                onClick={() => setActiveDocument(source.document_id)}
              >
                {source.document_id}
              </button>
            ))}
          </div>
        )}
        {activeSource ? (
          <TracePage documentId={activeSource.document_id} source={activeSource} />
        ) : (
          <p className={styles.loading}>No document sources for this line.</p>
        )}
      </div>
    </div>
  );
}
