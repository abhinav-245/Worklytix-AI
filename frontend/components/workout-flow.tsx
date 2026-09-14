"use client";

import { useEffect, useState } from "react";
import { CsvUpload } from "@/components/csv-upload";
import {
  OverviewGrid,
  type TrainingOverview,
} from "@/components/overview-grid";
import { PrTable, type ExercisePR } from "@/components/pr-table";
import {
  ProfileSection,
} from "@/components/profile-section";
import {
  MuscleSection,
  type MuscleAnalysis,
} from "@/components/muscle-section";
import {
  VarietySection,
  type ExerciseVariety,
} from "@/components/variety-section";
import {
  PlateauSection,
  type ExercisePlateau,
} from "@/components/plateau-section";
import {
  ProgressionSection,
  type ExerciseProgression,
} from "@/components/progression-charts";

import {
  getExerciseVariety,
  getMuscles,
  getOverview,
  getPlateaus,
  getPRs,
  getProgression,
} from "@/lib/api";

/**
 * Upload → analysis flow. All numbers are calculated by the backend;
 * this component only displays them.
 */
export function WorkoutFlow() {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [prs, setPrs] = useState<ExercisePR[] | null>(null);
  const [progression, setProgression] = useState<ExerciseProgression[] | null>(
    null
  );
  const [plateaus, setPlateaus] = useState<ExercisePlateau[] | null>(null);
  const [muscles, setMuscles] = useState<MuscleAnalysis | null>(null);
  const [variety, setVariety] = useState<ExerciseVariety | null>(null);
  const [profileVersion, setProfileVersion] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    getOverview().then((data) => {
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
    getPRs().then((data) => {
      if (!active) return;
      setPrs(data);
    });
    return () => {
      active = false;
    };
  }, [overview, profileVersion]);

  useEffect(() => {
    if (!overview) return;
    let active = true;
    getProgression().then((data) => {
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
    getPlateaus().then((data) => {
      if (!active) return;
      setPlateaus(data);
    });
    return () => {
      active = false;
    };
  }, [overview]);

  useEffect(() => {
    if (!overview) return;
    let active = true;
    getMuscles().then((data) => {
      if (!active) return;
      setMuscles(data);
    });
    return () => {
      active = false;
    };
  }, [overview]);

  useEffect(() => {
    if (!overview) return;
    let active = true;
    getExerciseVariety().then((data) => {
      if (!active) return;
      setVariety(data);
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
      {muscles ? (
        <section className="flex w-full flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Muscles
          </h2>
          <MuscleSection analysis={muscles} />
        </section>
      ) : null}
      {variety ? (
        <section className="flex w-full flex-col items-center gap-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            Exercise Variety
          </h2>
          <VarietySection variety={variety} />
        </section>
      ) : null}
      <section className="flex w-full flex-col items-center gap-4">
        <h2 className="text-2xl font-semibold tracking-tight">Profile</h2>
        <ProfileSection
          onProfileSaved={() => setProfileVersion((v) => v + 1)}
        />
      </section>
    </>
  );
}
