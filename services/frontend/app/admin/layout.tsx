import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Admin Dashboard | BitMod",
  description: "Monitor your BitMod deployment: cache hit rates, latency metrics, ingested documents, provider usage, and real-time pipeline analytics.",
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children
}
