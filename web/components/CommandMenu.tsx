"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api-client";
import type { SearchResult } from "@/lib/types";
import styles from "./CommandMenu.module.css";

type Command = { label: string; run: () => void };

function hrefForResult(result: SearchResult): string {
  switch (result.type) {
    case "case":
      return `/cases/${result.id}`;
    case "line":
      return `/trace/line/${result.id}`;
    case "document":
      return `/documents/${result.id}`;
    case "note":
      return "/activity";
  }
}

/** Cmd/Ctrl+K command menu (docs/UX.md Top bar). Step 9 (B38): full
 * search across cases, lines, documents and review notes, plus the
 * original quick-navigation commands. */
export function CommandMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    function onOpenRequest() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("proofline:open-command-menu", onOpenRequest);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("proofline:open-command-menu", onOpenRequest);
    };
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const trimmed = query.trim();

  useEffect(() => {
    if (!open || trimmed.length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      apiFetch<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(trimmed)}`)
        .then((body) => {
          if (!cancelled) setResults(body.results);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        });
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, trimmed]);

  if (!open) return null;

  const commands: Command[] = [
    { label: "Go to queue", run: () => router.push("/queue") },
    { label: "Go to areas", run: () => router.push("/areas") },
    { label: "Go to documents", run: () => router.push("/documents") },
    { label: "Go to activity", run: () => router.push("/activity") },
  ];

  const filtered = commands.filter((command) =>
    command.label.toLowerCase().includes(trimmed.toLowerCase()),
  );

  function runAndClose(command: Command) {
    command.run();
    setOpen(false);
    setQuery("");
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (trimmed.startsWith("case-")) {
      runAndClose({ label: trimmed, run: () => router.push(`/cases/${trimmed}`) });
      return;
    }
    if (trimmed.startsWith("D") || trimmed.startsWith("d")) {
      runAndClose({ label: trimmed, run: () => router.push(`/documents/${trimmed.toUpperCase()}`) });
      return;
    }
    if (filtered[0]) runAndClose(filtered[0]);
  }

  return (
    <div className={styles.overlay} role="presentation" onClick={() => setOpen(false)}>
      <form
        className={styles.menu}
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        onClick={(event) => event.stopPropagation()}
        onSubmit={onSubmit}
      >
        <input
          ref={inputRef}
          className={styles.input}
          placeholder="Search cases, lines, documents, actions..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <ul className={styles.results}>
          {filtered.map((command) => (
            <li key={command.label}>
              <button type="button" className={styles.result} onClick={() => runAndClose(command)}>
                {command.label}
              </button>
            </li>
          ))}
          {results.map((result) => (
            <li key={`${result.type}-${result.id}`}>
              <button
                type="button"
                className={styles.result}
                onClick={() => runAndClose({ label: result.title, run: () => router.push(hrefForResult(result)) })}
              >
                <span className="mono">{result.type}</span> {result.title}
                <br />
                <small>{result.snippet}</small>
              </button>
            </li>
          ))}
          {filtered.length === 0 && results.length === 0 && (
            <li className={styles.hint}>
              Search cases, lines, documents and notes, or type a case id (case-...) or
              document id (D01) and press Enter.
            </li>
          )}
        </ul>
      </form>
    </div>
  );
}
