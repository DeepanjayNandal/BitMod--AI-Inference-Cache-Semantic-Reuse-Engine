"use client"

import { CopyButton } from "@/components/copy-button"

export function CodeBlock({ filename, children }: { filename?: string; children: string }) {
  return (
    <div className="group relative rounded-xl border border-border/60 bg-[#0d1117] overflow-hidden shadow-lg">
      {filename ? (
        <div className="flex items-center gap-2 border-b border-border/20 px-4 py-2.5">
          <div className="flex gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
            <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
            <div className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-muted-foreground ml-2 font-mono">{filename}</span>
          <div className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyButton text={children} />
          </div>
        </div>
      ) : (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <CopyButton text={children} />
        </div>
      )}
      <pre className="p-4 text-sm font-mono leading-relaxed overflow-x-auto">
        <code className="text-[#e6edf3]">{children}</code>
      </pre>
    </div>
  )
}
