import Link from "next/link";
import { CaseDetailPanel } from "@/components/CaseDetailPanel";

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div>
      <Link href="/queue" style={{ color: "var(--accent)", fontSize: 13 }}>
        ← Back to queue
      </Link>
      <div style={{ marginTop: 16 }}>
        <CaseDetailPanel caseId={id} />
      </div>
    </div>
  );
}
