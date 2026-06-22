"use client"

import { usePathname } from "next/navigation"
import { useEffect } from "react"

export function ScrollToTop() {
  const pathname = usePathname()

  // Disable browser scroll restoration
  useEffect(() => {
    if ("scrollRestoration" in history) {
      history.scrollRestoration = "manual"
    }
  }, [])

  // Scroll to top on route change (skip if URL has a hash anchor)
  useEffect(() => {
    if (!window.location.hash) {
      window.scrollTo(0, 0)
    }
  }, [pathname])

  return null
}
