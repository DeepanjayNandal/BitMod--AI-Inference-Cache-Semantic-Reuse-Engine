import type { Metadata } from "next"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import {
  Bug, GitPullRequest, Plug, BookOpen, ArrowRight,
  GitFork, GitBranch, Code, TestTube, CheckCircle2
} from "lucide-react"

export const metadata: Metadata = {
  title: "Contributing | BitMod",
  description: "Contribute to BitMod: report bugs, submit pull requests, build adapters, write docs, and help grow the open-source community.",
}

const contributionCards = [
  {
    icon: Bug,
    title: "Report Bugs",
    description: "Found an issue? Open a GitHub issue with reproduction steps and we'll investigate.",
    href: "https://github.com/BitModerator/bitmod/issues",
    buttonLabel: "Open an Issue",
  },
  {
    icon: GitPullRequest,
    title: "Fix Bugs",
    description: "Pick up an issue tagged \"good first issue\" and submit a pull request.",
    href: "https://github.com/BitModerator/bitmod/issues?q=label%3A%22good+first+issue%22",
    buttonLabel: "Find Issues",
  },
  {
    icon: Plug,
    title: "Add Adapters",
    description: "Build new LLM, database, or embedding provider adapters to expand BitMod's reach.",
    href: "https://github.com/BitModerator/bitmod/blob/main/CONTRIBUTING.md",
    buttonLabel: "Adapter Guide",
  },
  {
    icon: BookOpen,
    title: "Improve Docs",
    description: "Help make the documentation clearer, more comprehensive, and easier to follow.",
    href: "https://github.com/BitModerator/bitmod/blob/main/CONTRIBUTING.md",
    buttonLabel: "Docs Guide",
  },
]

const processSteps = [
  { icon: GitFork, label: "Fork", description: "Fork the repository to your GitHub account" },
  { icon: GitBranch, label: "Branch", description: "Create a feature branch from main" },
  { icon: Code, label: "Code", description: "Make your changes with clear, tested code" },
  { icon: TestTube, label: "Test", description: "Run the test suite and add tests for new code" },
  { icon: GitPullRequest, label: "PR", description: "Open a pull request with a clear description" },
]

export default function ContributingPage() {
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
              Contribute to BitMod
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            BitMod is built by its community. Whether you&apos;re fixing a typo, adding a feature,
            or reporting a bug, every contribution makes the project better for everyone.
          </p>
        </div>

        {/* How to Contribute */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            How to Contribute
          </h2>
          <p className="text-muted-foreground mb-8">
            There are many ways to get involved, regardless of your experience level.
          </p>

          <div className="grid gap-6 sm:grid-cols-2">
            {contributionCards.map((card) => (
              <Card key={card.title} className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <card.icon className="h-5 w-5 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{card.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-6">
                    {card.description}
                  </p>
                  <Button asChild variant="outline" className="w-full">
                    <a href={card.href} target="_blank" rel="noopener noreferrer">
                      {card.buttonLabel}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </a>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Quick Start for Contributors */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Quick Start for Contributors
          </h2>
          <p className="text-muted-foreground mb-8">
            Get a local development environment running in under a minute.
          </p>

          <div className="rounded-xl border border-border/60 bg-[#0d1117] overflow-hidden shadow-lg">
            <div className="flex items-center gap-2 border-b border-border/20 px-4 py-2.5">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
              </div>
              <span className="text-xs text-muted-foreground font-mono">terminal</span>
            </div>
            <pre className="p-6 text-sm font-mono text-gray-300 overflow-x-auto">
              <code>{`git clone https://github.com/BitModerator/bitmod.git
cd bitmod
pip install -e ".[dev]"
pytest tests/ -v`}</code>
            </pre>
          </div>
        </div>

        {/* Contribution Guidelines */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Contribution Guidelines
          </h2>
          <p className="text-muted-foreground mb-8">
            Follow this process to get your contribution merged.
          </p>

          <div className="grid gap-4 sm:grid-cols-5">
            {processSteps.map((step, index) => (
              <Card key={step.label} className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg text-center">
                <CardContent className="pt-6">
                  <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                    <step.icon className="h-5 w-5 text-primary" />
                  </div>
                  <div className="text-xs font-semibold text-muted-foreground mb-1">
                    Step {index + 1}
                  </div>
                  <div className="font-bold text-lg mb-1">{step.label}</div>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center">
          <h2 className="text-2xl font-bold">Ready to contribute?</h2>
          <p className="mt-2 text-muted-foreground">
            Read the full contributor guide for detailed instructions, coding standards, and review process.
          </p>
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button asChild>
              <a href="https://github.com/BitModerator/bitmod/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer">
                Full Contributing Guide
                <ArrowRight className="ml-2 h-4 w-4" />
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://github.com/BitModerator/bitmod/issues" target="_blank" rel="noopener noreferrer">
                Browse Open Issues
              </a>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
