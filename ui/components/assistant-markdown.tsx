"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function AssistantMarkdown({ content }: { content: string }) {
  return (
    <div className="assistant-markdown space-y-2 break-words text-sm leading-6 text-text-secondary">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="font-heading text-base font-semibold text-text-primary">{children}</h1>,
          h2: ({ children }) => <h2 className="font-heading text-sm font-semibold text-text-primary">{children}</h2>,
          h3: ({ children }) => <h3 className="font-heading text-sm font-semibold text-text-primary">{children}</h3>,
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
          em: ({ children }) => <em className="text-text-primary">{children}</em>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          code: ({ children, className }) => className
            ? <code className="block overflow-x-auto rounded-lg border border-border-subtle bg-surface-1 p-3 font-mono text-xs text-text-primary">{children}</code>
            : <code className="rounded border border-border-subtle bg-surface-1 px-1 py-0.5 font-mono text-[0.8em] text-accent">{children}</code>,
          blockquote: ({ children }) => <blockquote className="border-l-2 border-accent/50 pl-3 text-text-muted">{children}</blockquote>,
          a: ({ children, href }) => <a href={href} className="text-accent underline-offset-2 hover:underline">{children}</a>,
          hr: () => <hr className="border-border-subtle" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
