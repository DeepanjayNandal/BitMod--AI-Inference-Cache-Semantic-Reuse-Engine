import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <h2 className="text-4xl font-bold">404</h2>
      <p className="mt-2 text-lg text-muted-foreground">Page not found</p>
      <p className="mt-1 text-sm text-muted-foreground max-w-md">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Button asChild className="mt-6">
        <Link href="/">Back to home</Link>
      </Button>
    </div>
  )
}
