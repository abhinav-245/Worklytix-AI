"use client";

import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { NoDataset } from "@/components/no-dataset";
import { ProfileSection } from "@/components/profile-section";
import { SectionSkeleton } from "@/components/dashboard/section";
import { Card, CardContent } from "@/components/ui/card";

/** Dedicated profile route: form, validation, summary and history. */
export default function ProfilePage() {
  const [hasDataset, setHasDataset] = useState<boolean | null>(null);

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
        <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your details and observed training history.
        </p>
      </div>
      {hasDataset === null ? (
        <Card className="glass w-full">
          <CardContent className="pt-6">
            <SectionSkeleton rows={4} />
          </CardContent>
        </Card>
      ) : !hasDataset ? (
        <NoDataset context="your profile training history" />
      ) : (
        <div className="flex w-full justify-center">
          <ProfileSection />
        </div>
      )}
    </main>
  );
}
