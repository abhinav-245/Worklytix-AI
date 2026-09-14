import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type SectionStatus =
  | { state: "loading" }
  | { state: "ready" }
  | { state: "empty"; message: string }
  | { state: "error"; message: string };

/** Skeleton blocks approximating a section's final layout. */
export function SectionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div
      className="flex w-full flex-col gap-2"
      aria-label="Loading"
      role="status"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-10 w-full animate-pulse rounded-md bg-white/[0.06]"
        />
      ))}
    </div>
  );
}

/** Isolated section error with retry; never takes down the dashboard. */
export function SectionError({
  title,
  message,
  retry,
}: {
  title: string;
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="flex w-full flex-col items-start gap-3">
      <p className="text-sm text-muted-foreground">
        Unable to load {title.toLowerCase()} data. {message}
      </p>
      {retry ? (
        <Button variant="outline" size="sm" onClick={retry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

/** Consistent dashboard section shell: anchor, title, description, body. */
export function DashboardSection({
  id,
  title,
  description,
  status,
  children,
  className,
  retry,
}: {
  id: string;
  title: string;
  description?: string;
  status: SectionStatus;
  children: ReactNode;
  className?: string;
  retry?: () => void;
}) {
  return (
    <section
      id={id}
      aria-label={title}
      className={cn("flex w-full scroll-mt-24 flex-col gap-4", className)}
    >
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <Card className="glass w-full">
        <CardContent className="pt-6">
          {status.state === "loading" ? (
            <SectionSkeleton />
          ) : status.state === "error" ? (
            <SectionError
              title={title}
              message={status.message}
              retry={retry}
            />
          ) : status.state === "empty" ? (
            <p className="text-sm text-muted-foreground">{status.message}</p>
          ) : (
            children
          )}
        </CardContent>
      </Card>
    </section>
  );
}

/** Section header card variant for narrow intro blocks. */
export function SectionIntro({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <Card className="glass gold-accent-top w-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
    </Card>
  );
}
