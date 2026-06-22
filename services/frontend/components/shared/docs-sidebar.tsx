"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface SidebarLink {
  href: string
  label: string
  external?: boolean
}

interface SidebarSection {
  title: string
  links: SidebarLink[]
}

export function DocsSidebar({ sections }: { sections: SidebarSection[] }) {
  const [activeId, setActiveId] = useState("")

  useEffect(() => {
    const anchors = sections
      .flatMap((s) => s.links)
      .filter((l) => l.href.startsWith("#"))
      .map((l) => l.href.slice(1))

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the first visible section
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible.length > 0) {
          setActiveId(visible[0].target.id)
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    )

    anchors.forEach((id) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [sections])

  return (
    <nav className="hidden lg:block sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto pr-4">
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.title}>
            <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              {section.title}
            </h4>
            <ul className="space-y-0.5">
              {section.links.map((link) => {
                const isAnchor = link.href.startsWith("#")
                const isActive = isAnchor && activeId === link.href.slice(1)

                if (link.external || !isAnchor) {
                  return (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="block text-[13px] py-1 pl-3 border-l-2 border-transparent text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {link.label} {link.external ? "→" : ""}
                      </Link>
                    </li>
                  )
                }

                return (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      className={cn(
                        "block text-[13px] py-1 pl-3 border-l-2 transition-colors",
                        isActive
                          ? "border-primary text-foreground font-medium"
                          : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
                      )}
                    >
                      {link.label}
                    </a>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  )
}
