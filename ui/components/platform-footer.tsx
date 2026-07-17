import Link from "next/link";
import { Cable, Database, FileText, MessageCircleQuestion, Radio } from "lucide-react";

const guideLinks = [
  { href: "/help-guidance#sources", label: "Connect a source", icon: Cable },
  { href: "/help-guidance#pipeline", label: "Trace the event pipeline", icon: Radio },
  { href: "/help-guidance#historian", label: "Explore historian data", icon: Database },
  { href: "/help-guidance#datasets", label: "Prepare datasets", icon: FileText },
];

export function PlatformFooter() {
  return (
    <footer className="mt-auto border-t border-border-subtle bg-surface-1/80">
      <div className="mx-auto max-w-[1560px] px-4 py-8 md:py-10">
        <div className="grid gap-8 md:grid-cols-[1.3fr_repeat(3,minmax(0,1fr))]">
          <div className="space-y-4">
            <Link href="/" className="inline-flex items-center gap-3 rounded-lg focus-visible:outline-none">
              <span className="flex size-9 items-center justify-center rounded-lg border border-accent/40 bg-accent-subtle text-accent">
                <Radio aria-hidden="true" className="size-4" />
              </span>
              <span>
                <span className="block font-heading text-sm font-semibold tracking-tight text-text-primary">Ravan</span>
                <span className="block text-xs text-text-secondary">Industrial data control plane</span>
              </span>
            </Link>
            <p className="max-w-sm text-sm leading-6 text-text-secondary">
              A self-hosted foundation for collecting industrial events, processing them through Kafka and Flink, storing operational history, and preparing data for analytics and AI.
            </p>
            <p className="text-xs leading-5 text-text-muted">Open-source deployment. Your infrastructure, credentials, retention, and access policies remain under your control.</p>
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-text-primary">Start here</h2>
            <p className="text-xs leading-5 text-text-secondary">Open the full handbook for detailed instructions, ownership boundaries, and troubleshooting.</p>
            <nav aria-label="Platform setup guides" className="space-y-2">
              {guideLinks.map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} className="flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-accent">
                  <Icon aria-hidden="true" className="size-3.5 text-accent" />
                  {label}
                </Link>
              ))}
            </nav>
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-text-primary">How to operate</h2>
            <p className="text-xs leading-5 text-text-secondary">Connect and enable sources from Integrations. Confirm topics in Kafka UI, inspect metrics in Grafana and Prometheus, then use Historian for trends, SQL, replay, and exports.</p>
            <p className="text-xs leading-5 text-text-secondary">Operational briefings and dataset preparation are optional layers. They consume platform data; they do not replace the historian or event backbone.</p>
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-text-primary">Help and contact</h2>
            <p className="text-xs leading-5 text-text-secondary">For open-source support and deployment-specific questions, use the repository issue tracker first, and contact the maintainer directly only when needed.</p>
            <a href="mailto:navidmoradimehr3@gmail.com" className="flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-accent">
              <MessageCircleQuestion aria-hidden="true" className="size-4 text-accent" />
              navidmoradimehr3@gmail.com
            </a>
            <p className="text-xs leading-5 text-text-muted">When you open an issue, include the platform version, deployment profile, and relevant service logs. Do not include credentials.</p>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-border-subtle pt-4 text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} Ravan open-source project</span>
          <span>Self-hosted industrial data infrastructure</span>
        </div>
      </div>
    </footer>
  );
}
