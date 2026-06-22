import type { Metadata } from "next"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import {
  Heart, ArrowRight, Zap, Star, Users,
  Code, Globe, Shield, CheckCircle
} from "lucide-react"
import { GithubIcon } from "@/components/icons"

export const metadata: Metadata = {
  title: "Sponsor | BitMod",
  description: "Support BitMod open-source development. Sponsorships fund new features, infrastructure, and keep the project free and independent.",
}

const whySponsor = [
  {
    icon: Code,
    title: "Sustain Development",
    description: "Full-time development, new adapters, performance optimization, and continuous improvement of the cache engine.",
  },
  {
    icon: Users,
    title: "Community Growth",
    description: "Documentation, tutorials, community support, events, and resources to help developers succeed with BitMod.",
  },
  {
    icon: Globe,
    title: "Open Source Mission",
    description: "Keep BitMod free, open, and accessible to everyone. No vendor lock-in, no paywalls, no compromises.",
  },
]

const tiers = [
  {
    name: "Backer",
    price: "$5/mo",
    description: "Support open source development",
    features: ["Support open source", "Name in README"],
    borderClass: "border-green-500/30 hover:border-green-500/60",
    bgClass: "bg-green-500/5",
    iconColor: "text-green-500",
    badgeClass: "bg-green-500/10 text-green-500 border-green-500/20",
  },
  {
    name: "Supporter",
    price: "$25/mo",
    description: "Get closer to the project",
    features: ["Everything in Backer", "Priority issue responses", "Early access to features"],
    borderClass: "border-blue-500/30 hover:border-blue-500/60",
    bgClass: "bg-blue-500/5",
    iconColor: "text-blue-500",
    badgeClass: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  },
  {
    name: "Sponsor",
    price: "$100/mo",
    description: "Visible support with direct access",
    features: ["Everything in Supporter", "Logo on README + website", "Direct chat access"],
    borderClass: "border-accent/30 hover:border-accent/60",
    bgClass: "bg-accent/5",
    iconColor: "text-accent",
    badgeClass: "bg-accent/10 text-accent border-accent/20",
  },
  {
    name: "Enterprise Partner",
    price: "Custom",
    description: "Tailored partnership for your organization",
    features: ["Everything in Sponsor", "Custom adapter development", "Priority support SLA", "Architecture consulting"],
    borderClass: "border-primary/30 hover:border-primary/60",
    bgClass: "bg-primary/5",
    iconColor: "text-primary",
    badgeClass: "bg-primary/10 text-primary border-primary/20",
  },
]

const fundItems = [
  "New LLM provider adapters",
  "Database backend development",
  "Performance optimization & benchmarks",
  "Security audits",
  "Documentation & tutorials",
  "Community infrastructure",
  "CI/CD & testing infrastructure",
]

export default function SponsorPage() {
  return (
    <div className="relative">
      {/* Gradient background effect */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute right-1/4 top-1/4 h-[400px] w-[400px] rounded-full bg-accent/8 blur-[100px]" />
      </div>

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 text-center">
        <Badge variant="accent" className="mb-6 px-4 py-1.5 text-sm">
          Community
        </Badge>

        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl flex items-center justify-center gap-4">
          <Heart className="h-10 w-10 text-primary sm:h-12 sm:w-12" />
          <span>
            Support{" "}
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              BitMod
            </span>
          </span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
          BitMod is 100% open source. Your sponsorship helps us build the future of AI infrastructure.
        </p>
      </section>

      {/* Why Sponsor */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="accent" className="mb-4">
            Why Sponsor
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Your support makes a difference
          </h2>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          {whySponsor.map((item) => (
            <Card key={item.title} className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
              <CardHeader>
                <item.icon className="h-10 w-10 text-primary mb-2" />
                <CardTitle className="text-xl">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">{item.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Sponsorship Tiers */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="accent" className="mb-4">
            Tiers
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Choose your level of support
          </h2>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {tiers.map((tier) => (
            <Card
              key={tier.name}
              className={`${tier.borderClass} ${tier.bgClass} transition-all duration-300 hover:shadow-lg relative overflow-hidden`}
            >
              <div className={`absolute inset-0 bg-gradient-to-b from-transparent to-transparent via-transparent opacity-0 hover:opacity-100 transition-opacity duration-300`} />
              <CardHeader className="relative">
                <Badge className={tier.badgeClass}>{tier.name}</Badge>
                <div className="mt-4">
                  <span className="text-3xl font-bold">{tier.price}</span>
                </div>
                <CardDescription className="mt-2">{tier.description}</CardDescription>
              </CardHeader>
              <CardContent className="relative">
                <ul className="space-y-3">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <CheckCircle className={`h-5 w-5 shrink-0 mt-0.5 ${tier.iconColor}`} />
                      <span className="text-sm text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-6">
                  <Button asChild variant={tier.name === "Enterprise Partner" ? "default" : "outline"} className="w-full">
                    {tier.name === "Enterprise Partner" ? (
                      <Link href="/contact">
                        Contact Us <ArrowRight className="ml-2 h-4 w-4" />
                      </Link>
                    ) : (
                      <a href="https://github.com/sponsors/BitModerator" target="_blank" rel="noopener noreferrer">
                        Sponsor <ArrowRight className="ml-2 h-4 w-4" />
                      </a>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* What Your Support Funds */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="accent" className="mb-4">
            Impact
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            What your support funds
          </h2>
        </div>

        <Card className="border-border/40 bg-card/50 mx-auto max-w-2xl">
          <CardContent className="pt-6">
            <ul className="space-y-4">
              {fundItems.map((item) => (
                <li key={item} className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                  <span className="text-foreground">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </section>

      {/* Sponsor CTA */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Card className="border-primary/20 bg-primary/5 mx-auto max-w-2xl text-center">
          <CardContent className="py-12 px-8">
            <Heart className="h-16 w-16 text-primary mx-auto mb-6" />
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
              Become a{" "}
              <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                Sponsor
              </span>
            </h2>
            <p className="text-muted-foreground text-lg mb-8 max-w-lg mx-auto">
              Join the community of developers and organizations helping build the future of open-source AI infrastructure.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button size="lg" asChild>
                <a href="https://github.com/sponsors/BitModerator" target="_blank" rel="noopener noreferrer">
                  <GithubIcon className="mr-2 h-5 w-5" />
                  Sponsor on GitHub
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/docs">
                  <Zap className="mr-2 h-5 w-5" />
                  Read the Docs
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
