"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TraceContent } from "@/components/TraceContent";

/** The full-page version of S4 (docs/UX.md: "or full page at
 * /trace/line/{key}"). Navigating to an input/used-by line updates both
 * the on-screen trace and the URL, so the page stays a real deep link. */
export function TraceLineClient({ initialKey }: { initialKey: string }) {
  const router = useRouter();
  const [key, setKey] = useState(initialKey);

  function navigate(nextKey: string) {
    setKey(nextKey);
    router.replace(`/trace/line/${nextKey}`);
  }

  return (
    <div>
      <h1 style={{ marginBottom: 16 }} className="mono">
        Trace {key}
      </h1>
      <TraceContent lineKey={key} onNavigate={navigate} />
    </div>
  );
}
