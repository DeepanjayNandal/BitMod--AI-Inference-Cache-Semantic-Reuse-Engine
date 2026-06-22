import type { Metadata } from "next"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Play, Brain, Lock, Repeat, ArrowRight, Zap, Search, Shield,
  RefreshCw, CheckCircle, Settings, Hash
} from "lucide-react"
import { CodeBlock } from "@/components/shared/code-block"

export const metadata: Metadata = {
  title: "Assembly Engine | BitMod",
  description: "AI agents reason once, plans are cached and replayed deterministically. Zero LLM calls on repeat tasks with HMAC-signed, tamper-proof action plans.",
}

export default function AssemblyEnginePage() {
  return (
    <div className="relative">
      {/* Gradient background effect */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-accent/10 blur-[120px]" />
        <div className="absolute right-1/4 top-1/4 h-[400px] w-[400px] rounded-full bg-primary/8 blur-[100px]" />
      </div>

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-4 pt-20 pb-16 sm:px-6 sm:pt-28 sm:pb-24 lg:px-8">
        <div className="text-center">
          <Badge variant="outline" className="mb-3 px-4 py-1.5 text-sm border-amber-500/50 text-amber-400">
            Coming Soon — Phase 5
          </Badge>

          <Badge variant="accent" className="mb-6 ml-2 px-4 py-1.5 text-sm">
            Product Preview
          </Badge>

          <h1 className="text-5xl font-extrabold tracking-tight sm:text-7xl">
            <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
              Assembly Engine
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
            AI agents reason once. Plans are cached and replayed deterministically — zero LLM calls on repeat.
          </p>

          <p className="mx-auto mt-3 max-w-xl text-sm text-amber-400/80">
            This feature is planned for Phase 5 and is not yet available. The details below describe the intended design.
          </p>
        </div>
      </section>

      {/* Visual Flow Diagram */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            The Agent Loop
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            From task request to deterministic execution
          </p>
        </div>

        <div className="mx-auto max-w-3xl">
          <div className="rounded-2xl border border-border/40 bg-card/30 backdrop-blur-sm p-8">
            {/* Task Request enters */}
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 rounded-lg bg-accent/10 border border-accent/20 px-5 py-2.5 text-accent font-semibold arch-node">
                <Play className="h-4 w-4" />
                Task Request
              </div>
              <div className="mt-1 text-[10px] text-muted-foreground font-mono">&ldquo;Summarize Q3 reports and email team&rdquo;</div>
              <div className="mt-3 flex justify-center">
                <div className="w-px h-8 bg-gradient-to-b from-accent/60 to-accent/20 animate-flow-pulse" />
              </div>
            </div>

            {/* Plan Cache Lookup */}
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 rounded-lg bg-[#161b22] border border-border/30 px-5 py-3 text-[#e6edf3] font-semibold arch-node">
                <Search className="h-4 w-4 text-accent" />
                Plan Cache Lookup
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {[
                  { label: "Normalize Task", delay: "0s" },
                  { label: "Lookup", delay: "0.1s" },
                  { label: "HMAC Verify", delay: "0.2s" },
                  { label: "Param Injection", delay: "0.3s" },
                ].map((step) => (
                  <div
                    key={step.label}
                    className="rounded-md bg-muted/20 border border-border/20 px-2.5 py-1 text-center arch-node"
                    style={{ animationDelay: step.delay }}
                  >
                    <span className="text-[10px] text-muted-foreground">{step.label}</span>
                  </div>
                ))}
              </div>

              {/* Split into HIT / MISS */}
              <div className="mt-4 grid grid-cols-2 gap-8">
                {/* Plan HIT */}
                <div className="text-center flex-1">
                  <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-3 arch-node">
                    <div className="text-green-400 font-bold text-sm">PLAN HIT</div>
                    <div className="text-[10px] text-green-400/70 mt-1">HMAC valid &middot; replay steps</div>
                  </div>
                  <div className="mt-3 flex justify-center">
                    <div className="w-px h-6 bg-gradient-to-b from-green-400/40 to-green-400/20 animate-flow-pulse" style={{ animationDelay: "0.3s" }} />
                  </div>
                  <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-3 arch-node">
                    <div className="text-green-400 font-semibold text-xs">Deterministic Replay</div>
                    <div className="text-[10px] text-green-400/70 mt-1">No LLM call &middot; instant</div>
                  </div>
                </div>

                {/* Plan MISS */}
                <div className="text-center flex-1">
                  <div className="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 arch-node">
                    <div className="text-accent font-bold text-sm">PLAN MISS</div>
                    <div className="text-[10px] text-accent/70 mt-1">LLM generates plan &darr;</div>
                  </div>
                  <div className="mt-3 flex justify-center">
                    <div className="w-px h-6 bg-gradient-to-b from-accent/40 to-accent/20 animate-flow-pulse" style={{ animationDelay: "0.4s" }} />
                  </div>
                </div>
              </div>
            </div>

            {/* MISS path: LLM generates plan */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
                <Brain className="h-6 w-6 text-accent mx-auto mb-2" />
                <div className="text-sm font-semibold text-[#e6edf3]">LLM Reasoning</div>
                <div className="text-[10px] text-muted-foreground mt-1">
                  Generates step-by-step plan
                </div>
              </div>

              <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
                <Lock className="h-6 w-6 text-[#d2a8ff] mx-auto mb-2" />
                <div className="text-sm font-semibold text-[#e6edf3]">HMAC Signing</div>
                <div className="text-[10px] text-muted-foreground mt-1">
                  Each step cryptographically signed
                </div>
              </div>

              <div className="rounded-lg bg-[#161b22] border border-border/30 p-4 text-center arch-node">
                <CheckCircle className="h-6 w-6 text-green-400 mx-auto mb-2" />
                <div className="text-sm font-semibold text-[#e6edf3]">Execute &amp; Cache</div>
                <div className="text-[10px] text-muted-foreground mt-1">
                  Run tools, cache plan for replay
                </div>
              </div>
            </div>

            {/* Final: cached plan ready */}
            <div className="flex justify-center mb-3">
              <div className="w-px h-6 bg-gradient-to-b from-green-400/40 to-green-400/20 animate-flow-pulse" style={{ animationDelay: "0.7s" }} />
            </div>
            <div className="text-center">
              <div className="inline-flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-5 py-2.5 text-green-400 font-semibold text-sm arch-node">
                <Repeat className="h-4 w-4" />
                Similar tasks replay cached plan instantly
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="accent" className="mb-4">How It Works</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Reason once.{" "}
            <span className="text-accent">Replay forever.</span>
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            Four stages turn expensive agent reasoning into deterministic execution.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          {[
            {
              icon: Brain,
              title: "Plan Generation",
              description: "The LLM analyzes the task and generates an ordered sequence of steps with tool assignments. Each step specifies the tool, parameters, dependencies, and expected output shape.",
              color: "text-accent",
            },
            {
              icon: Lock,
              title: "HMAC Integrity",
              description: "Every plan step is cryptographically signed with HMAC-SHA256. Plans are tamper-proof, versioned, and verified before every replay. Any modification invalidates the entire chain.",
              color: "text-[#d2a8ff]",
            },
            {
              icon: Settings,
              title: "Parameter Injection",
              description: "Cached plans have typed parameter slots. When a similar task arrives, parameters are swapped in-place — \"Q3 reports\" becomes \"Q4 reports\" without re-reasoning the workflow.",
              color: "text-primary",
            },
            {
              icon: Repeat,
              title: "Deterministic Replay",
              description: "Same plan, same tools, same order — no LLM reasoning needed. Execution follows the cached step graph exactly, producing consistent results at zero inference cost.",
              color: "text-green-400",
            },
          ].map((card) => (
            <Card key={card.title} className="group relative overflow-hidden border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
              <CardHeader>
                <card.icon className={`h-10 w-10 ${card.color} mb-2`} />
                <CardTitle className="text-lg">{card.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {card.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Code Example */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            See it in action
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            The second call is free. Same workflow, zero LLM calls.
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
              <span className="text-xs text-muted-foreground ml-2 font-mono">assembly_engine.py</span>
            </div>
            <pre className="p-6 text-sm font-mono leading-relaxed overflow-x-auto">
              <code>
                <span className="text-[#8b949e] italic"># First call: LLM reasons + generates plan</span>{"\n"}
                <span className="text-[#e6edf3]">result</span> <span className="text-[#ff7b72]">=</span> <span className="text-[#e6edf3]">agent</span>.<span className="text-[#d2a8ff]">execute</span>(<span className="text-[#a5d6ff] brightness-110">&quot;Summarize Q3 reports and email team&quot;</span>){"\n"}
                <span className="text-[#8b949e] italic"># → Plan generated, signed, cached</span>{"\n"}
                {"\n"}
                <span className="text-[#8b949e] italic"># Second call: instant replay with new params</span>{"\n"}
                <span className="text-[#e6edf3]">result</span> <span className="text-[#ff7b72]">=</span> <span className="text-[#e6edf3]">agent</span>.<span className="text-[#d2a8ff]">execute</span>(<span className="text-[#a5d6ff] brightness-110">&quot;Summarize Q4 reports and email team&quot;</span>){"\n"}
                <span className="text-[#8b949e] italic"># → Cached plan replayed, zero LLM calls</span>
              </code>
            </pre>
          </div>
        </div>
      </section>

      {/* Security Section */}
      <section className="border-y border-border/40 bg-card/20">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <Badge variant="accent" className="mb-4">Security</Badge>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Cryptographic integrity.{" "}
              <span className="text-muted-foreground">No exceptions.</span>
            </h2>
            <p className="mt-3 text-lg text-muted-foreground">
              Every cached plan is tamper-proof and verified before replay.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Shield,
                title: "HMAC-SHA256 Signing",
                description: "Every step in the action plan is signed with HMAC-SHA256. Tampered plans are rejected before execution.",
              },
              {
                icon: Lock,
                title: "Tool Scope Enforcement",
                description: "Cached plans can only invoke the tools originally authorized. No scope escalation, no tool injection.",
              },
              {
                icon: Hash,
                title: "Plan Versioning",
                description: "Plans are versioned and pinned to their generating model. Model upgrades trigger re-generation, not stale replay.",
              },
              {
                icon: RefreshCw,
                title: "Auto Invalidation",
                description: "When source data changes, dependent plans are automatically invalidated. No stale workflows, no manual cache busting.",
              },
            ].map((item) => (
              <Card key={item.title} className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
                <CardHeader>
                  <item.icon className="h-8 w-8 text-accent mb-2" />
                  <CardTitle className="text-base">{item.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm leading-relaxed">
                    {item.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-b border-border/40 bg-card/30 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
            {[
              { value: "0", label: "LLM Calls on Replay", icon: Zap },
              { value: "100%", label: "Deterministic Execution", icon: Repeat },
              { value: "HMAC-SHA256", label: "Integrity", icon: Shield },
              { value: "Auto", label: "Invalidation", icon: RefreshCw },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <stat.icon className="mx-auto h-6 w-6 text-accent mb-2" />
                <div className="text-3xl font-bold text-foreground">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8 text-center">
        <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Stop paying for{" "}
          <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
            repeat reasoning
          </span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
          The Assembly Engine turns expensive agent workflows into instant, deterministic replays.
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
