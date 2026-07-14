import { Cable } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { SourceConnectionPanel } from "@/components/source-connection-panel";

export default function SourcesPage() {
  return <DashboardFrame><SectionHeader eyebrow="Data plane" title="Sources" description="Register and test the protocol bridges that feed the canonical event pipeline." /><SourceConnectionPanel /><div className="rounded-xl border border-border-subtle bg-surface-2 p-4 text-sm text-text-secondary"><Cable className="mb-2 size-5 text-accent" /><p>Save a source as metadata, test its network path, preview its fields, add mappings, then enable it. The edge runtime watches registry versions and activates supported connectors without a container restart.</p></div></DashboardFrame>;
}
