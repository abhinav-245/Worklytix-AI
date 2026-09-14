"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud } from "lucide-react";
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
import { saveProfile, uploadWorkoutCSV } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { FitnessGoal } from "@/components/profile-section";

const GOAL_LABELS: Record<FitnessGoal, string> = {
  muscle_gain: "Muscle Gain",
  strength: "Strength",
  fat_loss: "Fat Loss",
  general_fitness: "General Fitness",
};

const GOALS = Object.keys(GOAL_LABELS) as FitnessGoal[];

type OnboardingStatus =
  | { step: "idle" }
  | { step: "uploading" }
  | { step: "saving-profile" }
  | { step: "error"; message: string };

/**
 * Unified onboarding: CSV + age + body weight + goal submitted with one
 * "Upload & Analyze" action (CSV upload, then profile save, then
 * navigation). Validation errors come from the backend; nothing is
 * calculated here.
 */
export function Onboarding() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [age, setAge] = useState("");
  const [bodyWeight, setBodyWeight] = useState("");
  const [goal, setGoal] = useState<FitnessGoal>("general_fitness");
  const [status, setStatus] = useState<OnboardingStatus>({ step: "idle" });

  const busy = status.step === "uploading" || status.step === "saving-profile";

  const pickFile = (next: File | null) => {
    if (!next) return;
    setFile(next);
    if (status.step === "error") setStatus({ step: "idle" });
  };

  const submit = async () => {
    if (busy) return;
    if (!file) {
      setStatus({ step: "error", message: "Select a CSV file first." });
      return;
    }
    if (age.trim() === "" || bodyWeight.trim() === "") {
      setStatus({
        step: "error",
        message: "Enter your age and body weight to continue.",
      });
      return;
    }
    setStatus({ step: "uploading" });
    try {
      await uploadWorkoutCSV(file);
    } catch (err) {
      setStatus({
        step: "error",
        message: err instanceof Error ? err.message : "Upload failed.",
      });
      return;
    }
    setStatus({ step: "saving-profile" });
    try {
      await saveProfile({
        age: Number(age),
        body_weight_kg: Number(bodyWeight),
        goal,
      });
    } catch (err) {
      setStatus({
        step: "error",
        message: `Workout data uploaded, but the profile could not be saved: ${
          err instanceof Error ? err.message : "unknown error"
        }. Retry to save your profile.`,
      });
      return;
    }
    router.push("/overview");
  };

  return (
    <Card id="get-started" className="glass w-full max-w-md scroll-mt-24">
      <CardHeader>
        <CardTitle>Get Started</CardTitle>
        <CardDescription>Upload your Hevy CSV</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="CSV drop zone. Activate to browse for a file."
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            pickFile(e.dataTransfer.files?.[0] ?? null);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            dragOver
              ? "border-[var(--gold)] bg-[var(--gold-soft)]"
              : "border-white/15 hover:border-[var(--gold-soft)] hover:bg-white/[0.03]"
          )}
        >
          <UploadCloud
            className="h-8 w-8 text-[var(--gold)]"
            aria-hidden
          />
          <p className="text-sm font-medium">
            {file ? file.name : "CSV drop zone"}
          </p>
          <p className="text-xs text-muted-foreground">
            {file
              ? `${(file.size / 1024).toFixed(0)} KB selected — drop another file or click to replace`
              : "Drag & drop your CSV here, or click to browse"}
          </p>
          <Input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            tabIndex={-1}
            disabled={busy}
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <h3 className="text-sm font-medium">Your Details</h3>
        <div className="grid grid-cols-2 gap-4">
          <label
            htmlFor="onboarding-age"
            className="flex flex-col gap-2 text-sm font-medium"
          >
            Age
            <Input
              id="onboarding-age"
              type="number"
              min={1}
              step={1}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              disabled={busy}
            />
          </label>
          <label
            htmlFor="onboarding-weight"
            className="flex flex-col gap-2 text-sm font-medium"
          >
            Weight
            <span className="relative block">
              <Input
                id="onboarding-weight"
                type="number"
                min={0}
                step="any"
                value={bodyWeight}
                onChange={(e) => setBodyWeight(e.target.value)}
                disabled={busy}
                className="pr-10"
              />
              <span
                aria-hidden
                className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted-foreground"
              >
                kg
              </span>
            </span>
          </label>
        </div>
        <label
          htmlFor="onboarding-goal"
          className="flex flex-col gap-2 text-sm font-medium"
        >
          Goal
          <select
            id="onboarding-goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value as FitnessGoal)}
            disabled={busy}
            className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {GOALS.map((g) => (
              <option key={g} value={g}>
                {GOAL_LABELS[g]}
              </option>
            ))}
          </select>
        </label>

        <Button
          onClick={submit}
          disabled={busy}
          className="bg-[var(--gold)] font-semibold text-black hover:bg-[var(--gold)] hover:brightness-110"
        >
          {status.step === "uploading"
            ? "Uploading workout data…"
            : status.step === "saving-profile"
              ? "Saving profile…"
              : "Upload & Analyze"}
        </Button>

        {status.step === "error" ? (
          <Alert variant="destructive">
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>{status.message}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
