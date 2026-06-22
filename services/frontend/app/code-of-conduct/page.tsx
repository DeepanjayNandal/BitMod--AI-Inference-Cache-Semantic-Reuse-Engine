import type { Metadata } from "next"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import {
  Heart, MessageCircle, ThumbsUp, Users, Eye,
  HandHeart, ShieldAlert, ArrowRight, Scale, Mail
} from "lucide-react"

export const metadata: Metadata = {
  title: "Code of Conduct | BitMod",
  description: "BitMod community standards: inclusive language, respectful collaboration, and enforcement policies for a welcoming open-source environment.",
}

const positiveStandards = [
  {
    icon: MessageCircle,
    title: "Welcoming Language",
    description: "Using welcoming and inclusive language in all interactions.",
  },
  {
    icon: ThumbsUp,
    title: "Respect Differences",
    description: "Being respectful of differing viewpoints and experiences.",
  },
  {
    icon: HandHeart,
    title: "Accept Feedback",
    description: "Gracefully accepting constructive criticism and learning from it.",
  },
  {
    icon: Users,
    title: "Community First",
    description: "Focusing on what is best for the community as a whole.",
  },
  {
    icon: Eye,
    title: "Show Empathy",
    description: "Showing empathy towards other community members and their perspectives.",
  },
]

const unacceptableBehaviors = [
  "Trolling, insulting or derogatory comments, and personal or political attacks",
  "Public or private harassment of any kind",
  "Publishing others' private information without explicit permission",
  "The use of sexualized language or imagery and unwelcome attention or advances",
  "Other conduct which could reasonably be considered inappropriate in a professional setting",
]

export default function CodeOfConductPage() {
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
              Code of Conduct
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            We are committed to providing a welcoming, inclusive, and harassment-free
            experience for everyone in the BitMod community.
          </p>
        </div>

        {/* Our Pledge */}
        <div className="mb-20">
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="flex flex-col sm:flex-row items-center gap-6 py-8">
              <Heart className="h-12 w-12 text-primary shrink-0" />
              <div className="flex-1 text-center sm:text-left">
                <h2 className="text-xl font-bold">Our Pledge</h2>
                <p className="mt-2 text-muted-foreground">
                  We as members, contributors, and leaders pledge to make participation in our
                  community a harassment-free experience for everyone, regardless of age, body size,
                  visible or invisible disability, ethnicity, sex characteristics, gender identity
                  and expression, level of experience, education, socio-economic status, nationality,
                  personal appearance, race, caste, color, religion, or sexual identity and orientation.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Our Standards */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Our Standards
          </h2>
          <p className="text-muted-foreground mb-8">
            Examples of behavior that contributes to a positive environment.
          </p>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {positiveStandards.map((standard) => (
              <Card key={standard.title} className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <standard.icon className="h-5 w-5 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{standard.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {standard.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Unacceptable Behavior */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Unacceptable Behavior
          </h2>
          <p className="text-muted-foreground mb-8">
            The following behaviors are not tolerated in any community space.
          </p>

          <Card className="border-border/40 bg-card/50">
            <CardContent className="pt-6">
              <ul className="space-y-3">
                {unacceptableBehaviors.map((behavior) => (
                  <li key={behavior} className="flex items-start gap-3">
                    <ShieldAlert className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                    <span className="text-sm text-muted-foreground">{behavior}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Enforcement */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Enforcement
          </h2>
          <p className="text-muted-foreground mb-8">
            How violations are handled.
          </p>

          <Card className="border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300 hover:shadow-lg">
            <CardContent className="pt-6">
              <div className="space-y-4 text-sm text-muted-foreground">
                <p>
                  Community leaders are responsible for clarifying and enforcing our standards of
                  acceptable behavior and will take appropriate and fair corrective action in
                  response to any behavior that they deem inappropriate, threatening, offensive,
                  or harmful.
                </p>
                <p>
                  Community leaders have the right and responsibility to remove, edit, or reject
                  comments, commits, code, wiki edits, issues, and other contributions that are
                  not aligned to this Code of Conduct, and will communicate reasons for moderation
                  decisions when appropriate.
                </p>
                <p className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-primary shrink-0" />
                  <span>
                    Report violations to{" "}
                    <a href="mailto:security@bitmod.io" className="text-primary hover:underline font-medium">
                      security@bitmod.io
                    </a>
                    . All reports will be reviewed and investigated promptly and fairly.
                  </span>
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Attribution */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-2">
            Attribution
          </h2>
          <p className="text-muted-foreground mb-8">
            This Code of Conduct is adapted from the{" "}
            <a
              href="https://www.contributor-covenant.org/version/2/1/code_of_conduct/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Contributor Covenant, version 2.1
            </a>
            .
          </p>
        </div>

        {/* CTA */}
        <div className="text-center">
          <h2 className="text-2xl font-bold">Read the full Code of Conduct</h2>
          <p className="mt-2 text-muted-foreground">
            The complete Code of Conduct is available on GitHub.
          </p>
          <div className="mt-6">
            <Button asChild>
              <a href="https://github.com/BitModerator/bitmod/blob/main/CODE_OF_CONDUCT.md" target="_blank" rel="noopener noreferrer">
                Full Code of Conduct
                <ArrowRight className="ml-2 h-4 w-4" />
              </a>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
