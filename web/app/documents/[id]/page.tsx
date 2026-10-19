import { DocumentDetailClient } from "./DocumentDetailClient";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <DocumentDetailClient documentId={id} />;
}
