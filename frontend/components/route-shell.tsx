"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getOverview } from "@/lib/api";
import { useSection } from "@/components/use-section";
import { NoDataset } from "@/components/no-dataset";
import {
  SectionError,
  SectionSkeleton,
} from "@/components/dashboard/section";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Shared shell for analytics routes: dataset-presence check, then the
 * section fetch with isolated loading/error/empty states. Children render
 * only with real backend data.
 */
export function RouteShell<T>({
  title,
  description,
  context,
  fetcher,
  reloadKey,
  children,
}: {
  title: string;
  description: string;
  context: string;
  fetcher: () => Promise<T | null>;
  reloadKey?: unknown;
  children: (data: T) => ReactNode;
}) {
  const [hasDataset, setHasDataset] = useState<boolean | null>(null);
  const section = useSection(fetcher, hasDataset === true, reloadKey);

  useEffect(() => {
    let active = true;
    getOverview().then((overview) => {
      if (!active) return;
      setHasDataset(overview !== null);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      {hasDataset === null ? (
        <Card className="glass w-full">
          <CardContent className="pt-6">
            <SectionSkeleton rows={4} />
          </CardContent>
        </Card>
      ) : !hasDataset ? (
        <NoDataset context={context} />
      ) : section.status.state === "loading" ? (
        <Card className="glass w-full">
          <CardContent className="pt-6">
            <SectionSkeleton rows={4} />
          </CardContent>
        </Card>
      ) : section.status.state === "error" ? (
        <Card className="glass w-full">
          <CardContent className="pt-6">
            <SectionError
              title={title}
              message={section.status.message}
              retry={section.retry}
            />
          </CardContent>
        </Card>
      ) : section.data ? (
        children(section.data)
      ) : null}
    </main>
  );
}
