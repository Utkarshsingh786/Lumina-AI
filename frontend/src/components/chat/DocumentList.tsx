"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Loader2, CheckCircle2, XCircle, Trash2, FileType } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDocuments, useDeleteDocument } from "@/hooks/useDocuments";
import type { Document, DocumentStatus } from "@/types/api";

interface DocumentListProps {
  conversationId: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const STATUS_CONFIG: Record<
  DocumentStatus,
  { icon: React.ReactNode; label: string; className: string }
> = {
  pending: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    label: "Queued",
    className: "text-neutral-400",
  },
  indexing: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    label: "Indexing",
    className: "text-brand-400",
  },
  ready: {
    icon: <CheckCircle2 className="w-3 h-3" />,
    label: "Ready",
    className: "text-emerald-400",
  },
  error: {
    icon: <XCircle className="w-3 h-3" />,
    label: "Error",
    className: "text-red-400",
  },
};

function DocumentRow({
  doc,
  onDelete,
}: {
  doc: Document;
  onDelete: (id: string) => void;
}) {
  const status = STATUS_CONFIG[doc.status];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="group flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-800/60 border border-neutral-700/50"
    >
      <FileText className="w-3.5 h-3.5 text-neutral-500 flex-shrink-0" />

      <span className="flex-1 text-xs text-neutral-300 truncate" title={doc.filename}>
        {doc.filename}
      </span>

      <span className="text-xs text-neutral-600 flex-shrink-0">{formatBytes(doc.file_size)}</span>

      <span
        className={cn("flex items-center gap-1 text-xs flex-shrink-0", status.className)}
        title={doc.error_message ?? status.label}
      >
        {status.icon}
        <span className="hidden sm:inline">{status.label}</span>
      </span>

      <button
        onClick={() => onDelete(doc.id)}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-neutral-600 hover:text-red-400 transition-all flex-shrink-0"
        title="Remove document"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </motion.div>
  );
}

export function DocumentList({ conversationId }: DocumentListProps) {
  const { data: docs } = useDocuments(conversationId);
  const { mutate: deleteDoc } = useDeleteDocument(conversationId);

  if (!docs || docs.length === 0) return null;

  return (
    <div className="px-4 pb-2 space-y-1">
      <AnimatePresence mode="popLayout">
        {docs.map((doc) => (
          <DocumentRow key={doc.id} doc={doc} onDelete={deleteDoc} />
        ))}
      </AnimatePresence>
    </div>
  );
}
