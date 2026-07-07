"use client";

import Link from "next/link";
import { useEffect } from "react";
import { AlertTriangle, Home, RotateCcw } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function GlobalError({
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
    <html lang="en">
      <body className="bg-bg-main text-text-primary">
        <div className="mx-auto flex min-h-screen w-full max-w-3xl items-center justify-center px-4 py-10">
          <Card className="app-card w-full max-w-2xl">
            <CardHeader className="app-card-header">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <AlertTriangle className="size-4 text-error" />
                Fatal application error
              </CardTitle>
              <CardDescription className="text-text-secondary">
                The app failed before the local shell could recover. Reset the page or return to the main dashboard.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 p-4">
              <div className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm leading-6 text-text-primary">
                {error.message || "An unexpected global error occurred."}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={reset} className="inline-flex items-center gap-2">
                  <RotateCcw className="size-4" />
                  Reload app
                </Button>
                <Link href="/" className={buttonVariants({ variant: "outline" }) + " inline-flex items-center gap-2"}>
                  <Home className="size-4" />
                  Home
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </body>
    </html>
  );
}
