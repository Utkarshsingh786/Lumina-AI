"use client";

import React, { useCallback, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import { cn, copyToClipboard } from "@/lib/utils";

// ── Text extractor ────────────────────────────────────────────────────────────
// rehypeHighlight transforms code text into <span> elements. We recurse through
// the React node tree to extract the original plain text for our CodeBlock.
function extractText(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (React.isValidElement(node)) {
    return extractText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

// ── Code block ────────────────────────────────────────────────────────────────
interface CodeBlockProps {
  language: string;
  code: string;
}

function CodeBlock({ language, code }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const ok = await copyToClipboard(code);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [code]);

  return (
    <div className="relative group rounded-lg overflow-hidden border border-neutral-700 my-4">
      <div className="flex items-center justify-between px-4 py-2 bg-neutral-800 border-b border-neutral-700">
        <span className="text-xs font-mono text-neutral-400">{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-neutral-400 hover:text-white transition-colors"
          aria-label="Copy code"
        >
          {copied ? (
            <><Check className="w-3 h-3" /><span>Copied!</span></>
          ) : (
            <><Copy className="w-3 h-3" /><span>Copy</span></>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-sm bg-neutral-900 m-0">
        <code className={language ? `language-${language}` : ""}>{code}</code>
      </pre>
    </div>
  );
}

// ── Main renderer ─────────────────────────────────────────────────────────────
interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div
      className={cn(
        "prose prose-neutral dark:prose-invert max-w-none",
        "prose-pre:p-0 prose-pre:my-0 prose-pre:bg-transparent prose-pre:border-0",
        "prose-code:text-brand-400 prose-code:bg-neutral-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:before:content-none prose-code:after:content-none",
        "prose-headings:text-neutral-100",
        "prose-p:text-neutral-200 prose-li:text-neutral-200",
        "prose-a:text-brand-400 prose-a:no-underline hover:prose-a:underline",
        "prose-blockquote:border-brand-500 prose-blockquote:text-neutral-400",
        "prose-table:text-sm",
        "prose-hr:border-neutral-700",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const language = match?.[1] ?? "";

            // Extract raw text — children may be React elements (spans) if a
            // syntax highlighter plugin ran before us, so we recurse to get text.
            const codeText = extractText(children).replace(/\n$/, "");

            // Block code: has explicit language tag, OR is multi-line
            const isBlock = !!match || codeText.includes("\n");

            if (!isBlock) {
              // Inline code — render as-is
              return (
                <code className={cn("not-prose", className)} {...props}>
                  {children}
                </code>
              );
            }

            return <CodeBlock language={language} code={codeText} />;
          },

          // Open links in new tab
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },

          // Prevent prose from adding quotes around inline code
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
