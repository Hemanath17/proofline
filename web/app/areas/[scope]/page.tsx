import Link from "next/link";
import { AreaDetail } from "@/components/AreaDetail";

export default async function AreaPage({
  params,
}: {
  params: Promise<{ scope: string }>;
}) {
  const { scope } = await params;
  return (
    <div>
      <Link href="/areas" style={{ color: "var(--accent)", fontSize: 13 }}>
        ← Back to areas
      </Link>
      <div style={{ marginTop: 16 }}>
        <AreaDetail scope={scope} />
      </div>
    </div>
  );
}
