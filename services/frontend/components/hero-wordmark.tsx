"use client"

import { useState, useEffect } from "react"
import dynamic from "next/dynamic"
import { TerminalWordmark } from "@/components/terminal-logo"

const LazyAnimatedWordmark = dynamic(
  () => import("@/components/animated-wordmark").then(mod => ({ default: mod.AnimatedWordmark })),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-col items-center">
        <TerminalWordmark />
      </div>
    ),
  }
)

export function HeroWordmark({ className = "" }: { className?: string }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className={`flex flex-col items-center ${className}`}>
        <TerminalWordmark />
      </div>
    )
  }

  return <LazyAnimatedWordmark className={className} />
}
