"use client"

import Image from "next/image"
import { cn } from "@/lib/utils"

interface AnimatedLogoProps {
  size?: number
  className?: string
}

export function AnimatedLogo({ size = 40, className }: AnimatedLogoProps) {
  return (
    <div
      className={cn("relative inline-flex", className)}
      style={{ perspective: "600px" }}
    >
      <Image
        src="/logo.png"
        alt="BitMod"
        width={size}
        height={size}
        className="animated-logo-spin"
      />
    </div>
  )
}
