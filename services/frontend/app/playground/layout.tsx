import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Playground | BitMod",
  description: "Test your BitMod instance interactively. Send queries, inspect the 9-layer cache pipeline trace, and see cache hits and misses in real time.",
}

export default function PlaygroundLayout({ children }: { children: React.ReactNode }) {
  return children
}
