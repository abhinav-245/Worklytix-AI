import { Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

/** Insights placeholder: no AI functionality exists yet. */
export default function InsightsPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Insights</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI interpretation of your training, when it arrives.
        </p>
      </div>
      <Card className="glass gold-accent-top w-full">
        <CardContent className="flex flex-col items-center gap-3 px-6 py-12 text-center">
          <Sparkles
            className="h-8 w-8 text-[var(--gold)]"
            aria-hidden
          />
          <p className="text-lg font-semibold">Coming Soon</p>
          <p className="max-w-md text-sm text-muted-foreground">
            AI-powered interpretation will read the deterministic analytics
            on the other routes and explain them in plain language. Nothing
            here is generated or recommended today.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
