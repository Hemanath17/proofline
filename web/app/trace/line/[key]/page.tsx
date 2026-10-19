import { TraceLineClient } from "./TraceLineClient";

export default async function TraceLinePage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = await params;
  return <TraceLineClient initialKey={key} />;
}
