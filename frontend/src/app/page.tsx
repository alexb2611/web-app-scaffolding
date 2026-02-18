import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold">Welcome</h1>
        <p className="text-muted-foreground mt-2 text-lg">
          Your app is running. Get started below.
        </p>
      </div>

      <div className="flex gap-3">
        <Button asChild>
          <Link href="/login">Sign in</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/register">Create account</Link>
        </Button>
      </div>
    </main>
  );
}
