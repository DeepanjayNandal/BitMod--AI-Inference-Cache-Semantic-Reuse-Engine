import type { Metadata } from "next"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  ArrowRight, Brain, Database, Search, Cpu, Shuffle
} from "lucide-react"

export const metadata: Metadata = {
  title: "Any LLM, Any Database | BitMod",
  description: "Connect any LLM provider and any database backend with zero lock-in. 12 LLM adapters, 4 databases, 3 vector stores, all swappable without code changes.",
}

const providers = {
  llms: [
    "Anthropic", "OpenAI", "Gemini", "Ollama", "Bedrock", "Azure",
    "xAI", "Mistral", "Perplexity", "OpenRouter", "HuggingFace", "OpenAI-compatible",
  ],
  databases: ["SQLite", "PostgreSQL", "MySQL", "MongoDB"],
  vectorStores: ["ChromaDB", "Qdrant", "Pinecone"],
  embedders: ["Ollama", "Local (sentence-transformers)", "OpenAI", "Cohere"],
}

export default function AnyLlmAnyDbPage() {
  return (
    <div className="relative">
      {/* Gradient background effect */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute right-1/4 top-1/4 h-[400px] w-[400px] rounded-full bg-accent/8 blur-[100px]" />
      </div>

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-4 pt-20 pb-16 sm:px-6 sm:pt-28 sm:pb-24 lg:px-8">
        <div className="text-center">
          <Badge variant="accent" className="mb-6 px-4 py-1.5 text-sm">
            Solutions
          </Badge>

          <h1 className="text-5xl font-extrabold tracking-tight sm:text-7xl">
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Bring Your LLM.
            </span>
            <br />
            <span className="text-foreground">Bring Your Database.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
            BitMod doesn&apos;t pick your stack &mdash; you do.
            Use the LLM you trust, the database you run, the vector store you know.
            BitMod is infrastructure that wraps around your choices, not a platform that replaces them.
          </p>
        </div>
      </section>

      {/* Adapter Architecture Diagram */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Your stack. Our adapters.
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            Write to one interface. BitMod adapts to whatever you plug in.
          </p>
        </div>

        <div className="mx-auto max-w-3xl flex flex-col items-center">
          {/* Your Application */}
          <div className="inline-flex items-center gap-2 rounded-lg bg-primary/10 border border-primary/20 px-6 py-3 text-primary font-semibold arch-node">
            <Cpu className="h-5 w-5" />
            Your Application
          </div>

          {/* Connector */}
          <div className="w-px h-8 bg-gradient-to-b from-primary/60 to-primary/20 animate-flow-pulse" />

          {/* BitMod Stable Interfaces */}
          <div className="w-full rounded-xl border border-border/60 bg-[#0d1117] p-6 shadow-2xl">
            <div className="text-center mb-4">
              <div className="text-sm font-semibold text-[#e6edf3]">BitMod Stable Interfaces</div>
            </div>
            <div className="flex flex-wrap justify-center gap-3">
              <div className="rounded-lg bg-muted/30 border border-border/30 px-3 py-1.5 text-xs font-mono text-[#d2a8ff] arch-node">
                get_llm()
              </div>
              <div className="rounded-lg bg-muted/30 border border-border/30 px-3 py-1.5 text-xs font-mono text-[#79c0ff] arch-node">
                get_backend()
              </div>
              <div className="rounded-lg bg-muted/30 border border-border/30 px-3 py-1.5 text-xs font-mono text-[#ffa657] arch-node">
                get_embedder()
              </div>
            </div>
          </div>

          {/* Connector */}
          <div className="w-px h-8 bg-gradient-to-b from-accent/60 to-accent/20 animate-flow-pulse" style={{ animationDelay: "0.3s" }} />

          {/* Provider Cards Row */}
          <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
              <Brain className="h-6 w-6 text-[#d2a8ff] mx-auto mb-2" />
              <div className="text-sm font-semibold text-[#e6edf3]">Any LLM</div>
              <div className="text-xs text-[#8b949e] mt-1">Universal — any OpenAI-compatible provider</div>
            </div>
            <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
              <Database className="h-6 w-6 text-[#79c0ff] mx-auto mb-2" />
              <div className="text-sm font-semibold text-[#e6edf3]">4 Databases</div>
              <div className="text-xs text-[#8b949e] mt-1">SQLite, PostgreSQL, MySQL, MongoDB</div>
            </div>
            <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
              <Search className="h-6 w-6 text-[#ffa657] mx-auto mb-2" />
              <div className="text-sm font-semibold text-[#e6edf3]">3 Vector Stores</div>
              <div className="text-xs text-[#8b949e] mt-1">ChromaDB, Qdrant, Pinecone</div>
            </div>
            <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
              <Shuffle className="h-6 w-6 text-[#7ee787] mx-auto mb-2" />
              <div className="text-sm font-semibold text-[#e6edf3]">4 Embedders</div>
              <div className="text-xs text-[#8b949e] mt-1">Ollama, Local, OpenAI, Cohere</div>
            </div>
          </div>
        </div>
      </section>

      {/* Provider Grid */}
      <section className="border-y border-border/40 bg-card/20">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Already works with what you use
            </h2>
            <p className="mt-3 text-lg text-muted-foreground">
              Built-in adapters for the most popular providers. Need something else? Write an adapter in ~50 lines.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            {/* LLMs */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Brain className="h-5 w-5 text-[#d2a8ff]" />
                <span className="font-semibold text-foreground">LLM Providers</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {providers.llms.map((p) => (
                  <div key={p} className="rounded-md bg-muted/20 border border-border/30 px-2.5 py-1 text-xs font-mono text-[#e6edf3] arch-node">
                    {p}
                  </div>
                ))}
              </div>
            </div>

            {/* Databases */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Database className="h-5 w-5 text-[#79c0ff]" />
                <span className="font-semibold text-foreground">Databases</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {providers.databases.map((p) => (
                  <div key={p} className="rounded-md bg-muted/20 border border-border/30 px-2.5 py-1 text-xs font-mono text-[#e6edf3] arch-node">
                    {p}
                  </div>
                ))}
              </div>
            </div>

            {/* Vector Stores */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Search className="h-5 w-5 text-[#ffa657]" />
                <span className="font-semibold text-foreground">Vector Stores</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {providers.vectorStores.map((p) => (
                  <div key={p} className="rounded-md bg-muted/20 border border-border/30 px-2.5 py-1 text-xs font-mono text-[#e6edf3] arch-node">
                    {p}
                  </div>
                ))}
              </div>
            </div>

            {/* Embedders */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Shuffle className="h-5 w-5 text-[#7ee787]" />
                <span className="font-semibold text-foreground">Embedders</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {providers.embedders.map((p) => (
                  <div key={p} className="rounded-md bg-muted/20 border border-border/30 px-2.5 py-1 text-xs font-mono text-[#e6edf3] arch-node">
                    {p}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Code Example */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Swap providers with{" "}
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              env vars
            </span>
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            Zero code changes. Zero downtime. Zero risk.
          </p>
        </div>

        <div className="mx-auto max-w-3xl">
          <div className="rounded-xl border border-border/60 bg-[#0d1117] overflow-hidden shadow-2xl">
            <div className="flex items-center gap-2 border-b border-border/20 px-4 py-3">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
              </div>
              <span className="text-xs text-muted-foreground ml-2 font-mono">.env</span>
            </div>
            <pre className="p-6 text-sm font-mono leading-relaxed overflow-x-auto">
              <code>
                <span className="text-[#8b949e] italic"># Switch from OpenAI to Anthropic — zero code changes</span>{"\n"}
                <span className="text-[#a5d6ff]">BITMOD_LLM_PROVIDER</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">anthropic</span>{"\n"}
                <span className="text-[#a5d6ff]">ANTHROPIC_API_KEY</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">sk-ant-...</span>{"\n"}
                {"\n"}
                <span className="text-[#8b949e] italic"># Switch from SQLite to PostgreSQL</span>{"\n"}
                <span className="text-[#a5d6ff]">BITMOD_DB_BACKEND</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">postgresql</span>{"\n"}
                <span className="text-[#a5d6ff]">DATABASE_URL</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">postgresql://user:pass@host/db</span>{"\n"}
                {"\n"}
                <span className="text-[#8b949e] italic"># Switch vector store</span>{"\n"}
                <span className="text-[#a5d6ff]">BITMOD_VECTOR_STORE</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">qdrant</span>{"\n"}
                <span className="text-[#a5d6ff]">BITMOD_QDRANT_URL</span><span className="text-[#ff7b72]">=</span><span className="text-[#a5d6ff]">http://localhost:6333</span>
              </code>
            </pre>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8 text-center">
        <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Keep your stack.{" "}
          <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Add caching.
          </span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
          BitMod wraps around your existing infrastructure. Nothing to rip out, nothing to replace.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="xl" asChild>
            <Link href="/docs">
              Read the Docs <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
