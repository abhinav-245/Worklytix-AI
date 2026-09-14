"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { getOverview, getProfile } from "@/lib/api";
import type { ProfileAnalysis } from "@/components/profile-section";
import { DashboardHeader } from "@/components/dashboard/header";

function formatProfileLine(profile: ProfileAnalysis | null): string | null {
  if (!profile) return null;
  const goalLabels: Record<string, string> = {
    muscle_gain: "Muscle Gain",
    strength: "Strength",
    fat_loss: "Fat Loss",
    general_fitness: "General Fitness",
  };
  const parts = [goalLabels[profile.profile.goal] ?? profile.profile.goal];
  const history = profile.training_history;
  if (history) {
    parts.push(history.level, history.duration_text);
  }
  return parts.join(" · ");
}

/** Header with live dataset/profile status, refreshed on navigation. */
export function SiteHeader() {
  const pathname = usePathname();
  const [datasetLoaded, setDatasetLoaded] = useState(false);
  const [statusLine, setStatusLine] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getOverview().then((overview) => {
      if (!active) return;
      setDatasetLoaded(overview !== null);
    });
    getProfile().then((profile) => {
      if (!active) return;
      setStatusLine(formatProfileLine(profile));
    });
    return () => {
      active = false;
    };
  }, [pathname]);

  return (
    <DashboardHeader datasetLoaded={datasetLoaded} statusLine={statusLine} />
  );
}
