"use client"

import { Button } from "@/components/ui/button"

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <h2 className="text-2xl font-bold">Something went wrong</h2>
      <p className="mt-2 text-muted-foreground max-w-md">
        {error.message || "An unexpected error occurred."}
      </p>
      <Button onClick={reset} className="mt-6">
        Try again
      </Button>
    </div>
  )
}
