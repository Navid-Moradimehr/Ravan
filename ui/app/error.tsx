"use client";

import Link from "next/link";
import { useEffect } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-bg-main px-4 py-10 text-text-primary">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-3xl items-center justify-center">
        <Card className="app-card w-full max-w-2xl">
          <CardHeader className="app-card-header">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <AlertTriangle className="size-4 text-error" />
              Application error
            </CardTitle>
            <CardDescription className="text-text-secondary">
              The current view could not finish rendering. This usually means one of the live data sources or charts failed.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-4">
            <div className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm leading-6 text-text-primary">
              {error.message || "An unexpected error occurred."}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={reset} className="inline-flex items-center gap-2">
                <RotateCcw className="size-4" />
                Try again
              </Button>
              <Link href="/" className={buttonVariants({ variant: "outline" }) + " inline-flex items-center gap-2"}>
                <Home className="size-4" />
                Go home
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
