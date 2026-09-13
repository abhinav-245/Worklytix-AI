"use client";

import { useEffect, useState } from "react";
import { CsvUpload } from "@/components/csv-upload";
import {
  OverviewGrid,
  type TrainingOverview,
} from "@/components/overview-grid";
import { PrTable, type ExercisePR } from "@/components/pr-table";
import {
  PlateauSection,
  type ExercisePlateau,
} from "@/components/plateau-section";
import {
  ProgressionSection,
  type ExerciseProgression,
} from "@/components/progression-charts";

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

async function fetchProgression(): Promise<ExerciseProgression[] | null> {
  try {
    const res = await fetch(`${API_URL}/analysis/progression`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { exercises: ExerciseProgression[] };
    return body.exercises;
  } catch {
    return null;
  }
}

async function fetchPlateaus(): Promise<ExercisePlateau[] | null> {
  try {
    const res = await fetch(`${API_URL}/analysis/plateaus`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { plateaus: ExercisePlateau[] };
    return body.plateaus;
  } catch {
    return null;
  }
}

/**
 * Upload → overview + PRs + progression flow. All numbers are calculated
 * by the backend; this component only displays them.
 */
export function WorkoutFlow() {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [prs, setPrs] = useState<ExercisePR[] | null>(null);
  const [progression, setProgression] = useState<ExerciseProgression[] | null>(
    null
  );
  const [plateaus, setPlateaus] = useState<ExercisePlateau[] | null>(null);
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

  useEffect(() => {
    if (!overview) return;
    let active = true;
    fetchProgression().then((data) => {
      if (!active) return;
      setProgression(data);
    });
    return () => {
      active = false;
    };
  }, [overview]);

  useEffect(() => {
    if (!overview) return;
    let active = true;
    fetchPlateaus().then((data) => {
      if (!active) return;
      setPlateaus(data);
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
      {progression ? (
        <section className="flex w-full flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Progression
          </h2>
          <ProgressionSection exercises={progression} />
        </section>
      ) : null}
      {plateaus ? (
        <section className="flex w-full flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Plateaus
          </h2>
          <PlateauSection plateaus={plateaus} />
        </section>
      ) : null}
    </>
  );
}
