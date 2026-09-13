"use client";

import { useEffect, useState } from "react";
import { CsvUpload } from "@/components/csv-upload";
import {
  OverviewGrid,
  type TrainingOverview,
} from "@/components/overview-grid";
import { PrTable, type ExercisePR } from "@/components/pr-table";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchOverview(): Promise<TrainingOverview | null> {
  try {
    const res = await fetch(`${API_URL}/analysis/overview`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as TrainingOverview;
  } catch {
    return null;
  }
}

async function fetchPrs(): Promise<ExercisePR[] | null> {
  try {
    const res = await fetch(`${API_URL}/analysis/prs`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ExercisePR[];
  } catch {
    return null;
  }
}

/**
 * Upload → overview + PRs flow. All numbers are calculated by the backend;
 * this component only displays them.
 */
export function WorkoutFlow() {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [prs, setPrs] = useState<ExercisePR[] | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    fetchOverview().then((data) => {
      if (!active) return;
      setOverview(data);
      setLoaded(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!overview) return;
    let active = true;
    fetchPrs().then((data) => {
      if (!active) return;
      setPrs(data);
    });
    return () => {
      active = false;
    };
  }, [overview]);

  return (
    <>
      <CsvUpload onOverview={setOverview} />
      {overview ? (
        <section className="flex w-full flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Training Overview
          </h2>
          <OverviewGrid overview={overview} />
        </section>
      ) : loaded ? (
        <p className="max-w-md text-center text-sm text-muted-foreground">
          Upload a workout CSV to see your training overview.
        </p>
      ) : null}
      {prs ? (
        <section className="flex w-full max-w-3xl flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Personal Records
          </h2>
          <PrTable prs={prs} />
        </section>
      ) : null}
    </>
  );
}
