"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Status = "idle" | "loading" | "connected" | "not-connected";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("idle");
  const [detail, setDetail] = useState<string>("");

  const checkHealth = useCallback(async () => {
    setStatus("loading");
    setDetail("");
    try {
      const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as { status?: string };
      if (data.status === "ok") {
        setStatus("connected");
        setDetail(JSON.stringify(data));
      } else {
        setStatus("not-connected");
        setDetail(JSON.stringify(data));
      }
    } catch (err) {
      setStatus("not-connected");
      setDetail(err instanceof Error ? err.message : "Request failed");
    }
  }, []);

  const label =
    status === "connected"
      ? "Connected"
      : status === "not-connected"
        ? "Not Connected"
        : status === "loading"
          ? "Checking…"
          : "Not checked yet";

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Backend status: {label}</CardTitle>
        <CardDescription>
          Calls GET {API_URL}/health on the FastAPI backend.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Button onClick={checkHealth} disabled={status === "loading"}>
          {status === "loading" ? "Checking…" : "Check backend"}
        </Button>
        {detail ? (
          <p className="text-sm text-muted-foreground break-all">{detail}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
