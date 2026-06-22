import type { Metadata } from "next"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import {
  CheckCircle2, Circle, ArrowRight, Tag, Calendar,
  Sparkles, Layers, Database, Globe, FileText, Terminal,
  Server, Shield, LayoutDashboard, Rocket, Brain, Package, Plug
} from "lucide-react"

export const metadata: Metadata = {
  title: "Changelog | BitMod",
  description: "Track every BitMod release, feature, and improvement. View the latest version highlights and upcoming changes.",
}

const v020Features = [
  { icon: Brain, label: "Bayesian evidence accumulation cache engine — all 9 layers contribute graded confidence scores" },
  { icon: Globe, label: "Universal LLM adapter — 200+ providers via 3 env vars (URL, key, model)" },
  { icon: Sparkles, label: "Similarity link traversal — learned near-miss graph of related queries" },
  { icon: Layers, label: "Atomic fact search — reusable facts decomposed from prior answers" },
  { icon: Shield, label: "Security hardening — AES-256-GCM encryption at rest, RS256 JWT, token revocation" },
  { icon: Terminal, label: "CLI — doctor, backup, migrate, init --auto for zero-config setup" },
  { icon: LayoutDashboard, label: "Playground — multi-turn sessions, provider selector, localStorage persistence" },
  { icon: Rocket, label: "CI security scanning — gitleaks, pip-audit, semgrep, npm audit" },
]

const v010Features = [
  { icon: Layers, label: "9-layer intelligent cache engine" },
  { icon: Globe, label: "11 native LLM adapters + OpenAI-compatible universal adapter (12 total)" },
  { icon: Database, label: "4 database backends (SQLite, PostgreSQL, MySQL, MongoDB)" },
  { icon: Sparkles, label: "3 vector store integrations (ChromaDB, Qdrant, Pinecone)" },
  { icon: Server, label: "Multi-format proxy (OpenAI, Anthropic, Gemini)" },
  { icon: FileText, label: "Document ingestion (PDF, DOCX, HTML, Markdown, CSV, JSON, plain text)" },
  { icon: Terminal, label: "CLI toolkit (init, serve, ingest, query, status)" },
  { icon: Rocket, label: "Docker Compose deployment with profiles" },
  { icon: Shield, label: "API key authentication + JWT tokens" },
  { icon: LayoutDashboard, label: "Admin dashboard + interactive playground" },
  { icon: Package, label: "Python SDK (bitmod-client) with sync + async support" },
  { icon: Plug, label: "5 messaging integrations (Slack, Discord, Telegram, WhatsApp, Matrix)" },
]

const v030Preview = [
  "Cache profiler CLI — bitmod cache-profile to identify optimization opportunities",
  "Custom cache layer ordering — user-configurable priority per deployment",
  "Tier-based rate limiting — handle burst traffic gracefully",
  "One-click deploy configs (Railway, Render, Vercel)",
  "Comprehensive getting-started tutorial",
  "Interactive demo on bitmod.io",
]

export default function ChangelogPage() {
  return (
    <div className="relative">
      {/* Gradient background effect */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute right-1/4 top-1/4 h-[400px] w-[400px] rounded-full bg-accent/8 blur-[100px]" />
      </div>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        {/* Hero */}
        <div className="text-center mb-16">
          <Badge variant="accent" className="mb-4">Community</Badge>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              What&apos;s New in BitMod
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            Track every release, feature, and improvement. Built in the open,
            shipped when it&apos;s ready.
          </p>
        </div>

        {/* Latest Release — v0.2.0 */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-8">
            Latest Release
          </h2>

          <Card className="border-primary/20 bg-card/50 hover:border-primary/40 transition-all duration-300 hover:shadow-lg">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <Tag className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-xl">v0.2.0 — Bayesian Cache Engine + Universal LLM</CardTitle>
                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5" />
                      March 29, 2026
                    </div>
                  </div>
                </div>
                <Badge className="bg-green-500/10 text-green-500 border-green-500/20 self-start">
                  Latest
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {v020Features.map((feature) => (
                  <li key={feature.label} className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
                    <span className="text-sm text-foreground">{feature.label}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Previous Release — v0.1.0 */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-8">
            Previous Releases
          </h2>

          <Card className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/10">
                    <Tag className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <CardTitle className="text-xl">v0.1.0 — Initial Release</CardTitle>
                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5" />
                      March 22, 2026
                    </div>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {v010Features.map((feature) => (
                  <li key={feature.label} className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
                    <span className="text-sm text-foreground">{feature.label}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Coming Soon — v0.3.0 */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-8">
            Coming Soon
          </h2>

          <Card className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                    <Sparkles className="h-5 w-5 text-accent" />
                  </div>
                  <div>
                    <CardTitle className="text-xl">v0.3.0 — Open-Source Polish</CardTitle>
                  </div>
                </div>
                <Badge variant="outline" className="self-start">Upcoming</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {v030Preview.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Circle className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                    <span className="text-sm text-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* CTAs */}
        <div className="text-center">
          <h2 className="text-2xl font-bold">Stay up to date</h2>
          <p className="mt-2 text-muted-foreground">
            View the full changelog on GitHub or check the roadmap to see what&apos;s planned next.
          </p>
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button asChild>
              <a href="https://github.com/BitModerator/bitmod/blob/main/CHANGELOG.md" target="_blank" rel="noopener noreferrer">
                Full Changelog
                <ArrowRight className="ml-2 h-4 w-4" />
              </a>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/roadmap">
                View Roadmap
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
