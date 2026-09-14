"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type FitnessGoal =
  | "muscle_gain"
  | "strength"
  | "fat_loss"
  | "general_fitness";

const GOAL_LABELS: Record<FitnessGoal, string> = {
  muscle_gain: "Muscle Gain",
  strength: "Strength",
  fat_loss: "Fat Loss",
  general_fitness: "General Fitness",
};

const GOALS = Object.keys(GOAL_LABELS) as FitnessGoal[];

/** Mirrors backend ProfileAnalysis (analytics/profile.py). Display only. */
export interface ProfileAnalysis {
  profile: {
    age: number;
    body_weight_kg: number;
    goal: FitnessGoal;
  };
  training_history: {
    start_date: string;
    end_date: string;
    duration_days: number;
    duration_text: string;
    level: string;
  } | null;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    Array.isArray((body as { detail: unknown }).detail)
  ) {
    const first = (body as { detail: Array<{ msg?: unknown }> }).detail[0];
    if (first && typeof first.msg === "string") return first.msg;
  }
  if (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    typeof (body as { detail: unknown }).detail === "string"
  ) {
    return (body as { detail: string }).detail;
  }
  return fallback;
}

/**
 * Profile form + summary. Sends raw input to POST /profile and renders
 * only backend-validated, backend-calculated values.
 */
export function ProfileSection({
  onProfileSaved,
}: {
  onProfileSaved?: () => void;
}) {
  const [age, setAge] = useState("");
  const [bodyWeight, setBodyWeight] = useState("");
  const [goal, setGoal] = useState<FitnessGoal>("general_fitness");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ProfileAnalysis | null>(null);

  const submit = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: age === "" ? null : Number(age),
          body_weight_kg: bodyWeight === "" ? null : Number(bodyWeight),
          goal,
        }),
      });
      const body = (await res.json().catch(() => null)) as unknown;
      if (!res.ok) {
        setError(extractErrorMessage(body, `Save failed (HTTP ${res.status}).`));
        return;
      }
      setAnalysis(body as ProfileAnalysis);
      onProfileSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network request failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Your Profile</CardTitle>
        <CardDescription>
          Stored in memory for this session. Used for bodyweight-relative
          PR metrics.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <label
          htmlFor="profile-age"
          className="flex flex-col gap-2 text-sm font-medium"
        >
          Age
          <Input
            id="profile-age"
            type="number"
            min={1}
            step={1}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            disabled={saving}
          />
        </label>
        <label
          htmlFor="profile-weight"
          className="flex flex-col gap-2 text-sm font-medium"
        >
          Body Weight (kg)
          <Input
            id="profile-weight"
            type="number"
            min={0}
            step="any"
            value={bodyWeight}
            onChange={(e) => setBodyWeight(e.target.value)}
            disabled={saving}
          />
        </label>
        <label
          htmlFor="profile-goal"
          className="flex flex-col gap-2 text-sm font-medium"
        >
          Goal
          <select
            id="profile-goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value as FitnessGoal)}
            disabled={saving}
            className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {GOALS.map((g) => (
              <option key={g} value={g}>
                {GOAL_LABELS[g]}
              </option>
            ))}
          </select>
        </label>
        <Button onClick={submit} disabled={saving}>
          {saving ? "Saving…" : "Save profile"}
        </Button>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Could not save profile</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {analysis ? (
          <div className="flex flex-col gap-1 text-sm">
            <p>
              <span className="text-muted-foreground">Age: </span>
              <span className="font-medium">{analysis.profile.age}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Body Weight: </span>
              <span className="font-medium">
                {analysis.profile.body_weight_kg.toLocaleString("en-US")} kg
              </span>
            </p>
            <p>
              <span className="text-muted-foreground">Goal: </span>
              <span className="font-medium">
                {GOAL_LABELS[analysis.profile.goal]}
              </span>
            </p>
            {analysis.training_history ? (
              <>
                <p>
                  <span className="text-muted-foreground">
                    Training History:{" "}
                  </span>
                  <span className="font-medium">
                    {analysis.training_history.duration_text}
                  </span>
                </p>
                <p>
                  <span className="text-muted-foreground">
                    Observed training-history level:{" "}
                  </span>
                  <span className="font-medium">
                    {analysis.training_history.level}
                  </span>
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">
                Upload workout data to see training history.
              </p>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
