"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AIConversation,
  type ConversationTurn,
} from "@/components/ai-conversation";
import { NoDataset } from "@/components/no-dataset";
import {
  MOCK_ANALYSIS,
  MOCK_RECOMMENDATIONS,
  mockFollowUp,
} from "@/lib/ai-mock";
import {
  AskAIError,
  analyzeTraining,
  askAI,
  recommendTraining,
  getOverview,
  getProfile,
  type AIAnswer,
  type AIRecommendations,
  type ChatTurn,
} from "@/lib/api";

type LoadState =
  | { step: "checking" }
  | { step: "no-dataset" }
  | { step: "no-profile" }
  | { step: "ready" };

type PendingAction =
  | { type: "analyze" }
  | { type: "recommend" }
  | { type: "question"; text: string };

function recommendationsMarkdown(data: AIRecommendations): string {
  const lines = [
    "## Recommendations",
    "",
    "Based on your training history, goal, and the patterns above, "
    + "these are the highest-value areas worth considering:",
  ];
  data.recommendations.forEach((rec, i) => {
    lines.push("", `### ${i + 1}. ${rec.recommendation}`, "", rec.reason);
  });
  if (data.limitations.length > 0) {
    lines.push("", "Limitations:", "");
    data.limitations.forEach((limitation) => {
      lines.push(`- ${limitation}`);
    });
  }
  return lines.join("\n");
}

function historyFromTurns(turns: ConversationTurn[]): ChatTurn[] {
  return turns.slice(-20).map((turn) => ({
    role: turn.role,
    content: turn.content,
  }));
}

/** AI Analysis: conversational training intelligence. */
export default function AIAnalysisPage() {
  const [load, setLoad] = useState<LoadState>({ step: "checking" });
  const [mock] = useState(
    () =>
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("e2e_mock") === "1"
  );
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [analysisText, setAnalysisText] = useState<string | null>(null);
  const [recommendationsDone, setRecommendationsDone] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [sending, setSending] = useState(false);
  const [recommending, setRecommending] = useState(false);
  const nextId = useRef(1);
  const turnsRef = useRef<ConversationTurn[]>([]);
  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);

  const pushTurn = useCallback((turn: Omit<ConversationTurn, "id">) => {
    const id = nextId.current;
    nextId.current += 1;
    setTurns((prev) => [...prev, { ...turn, id }]);
  }, []);

  const fail = useCallback((err: unknown, action: PendingAction) => {
    setError(
      err instanceof AskAIError
        ? err.message
        : "I couldn't get an answer right now. Please try again."
    );
    setPending(action);
    setStatusText(null);
    setSending(false);
    setRecommending(false);
  }, []);

  const runAnalyze = useCallback(async () => {
    setError(null);
    setPending(null);
    setSending(true);
    setStatusText("Analyzing your training history…");
    try {
      const answer: AIAnswer = mock
        ? await new Promise<AIAnswer>((resolve) =>
            setTimeout(() => resolve(MOCK_ANALYSIS), 200)
          )
        : await analyzeTraining();
      setAnalysisText(answer.answer);
      pushTurn({
        role: "assistant",
        label: "Analysis",
        content: answer.answer,
      });
      setStatusText(null);
    } catch (err) {
      fail(err, { type: "analyze" });
      return;
    }
    setSending(false);
  }, [fail, mock, pushTurn]);

  const runRecommend = useCallback(async () => {
    if (!analysisText || recommending) return;
    setError(null);
    setPending(null);
    setRecommending(true);
    setStatusText("Preparing recommendations…");
    try {
      const data: AIRecommendations = mock
        ? await new Promise<AIRecommendations>((resolve) =>
            setTimeout(() => resolve(MOCK_RECOMMENDATIONS), 200)
          )
        : await recommendTraining(analysisText);
      pushTurn({
        role: "assistant",
        label: "Recommendations",
        content: recommendationsMarkdown(data),
      });
      setRecommendationsDone(true);
      setStatusText(null);
    } catch (err) {
      fail(err, { type: "recommend" });
      return;
    }
    setRecommending(false);
  }, [analysisText, fail, mock, pushTurn, recommending]);

  const runQuestion = useCallback(
    async (text: string) => {
      pushTurn({ role: "user", content: text });
      setError(null);
      setPending(null);
      setSending(true);
      setStatusText("Thinking…");
      try {
        const history = historyFromTurns(turnsRef.current);
        const answer: AIAnswer = mock
          ? await new Promise<AIAnswer>((resolve) =>
              setTimeout(() => resolve(mockFollowUp(text)), 200)
            )
          : await askAI(text, history);
        pushTurn({ role: "assistant", content: answer.answer });
        setStatusText(null);
      } catch (err) {
        fail(err, { type: "question", text });
        return;
      }
      setSending(false);
    },
    [fail, mock, pushTurn]
  );

  useEffect(() => {
    if (
      new URLSearchParams(window.location.search).get("e2e_mock") === "1"
    ) {
      return;
    }
    let active = true;
    Promise.all([getOverview(), getProfile()]).then(
      ([overview, profile]) => {
        if (!active) return;
        if (overview === null) setLoad({ step: "no-dataset" });
        else if (profile === null) setLoad({ step: "no-profile" });
        else setLoad({ step: "ready" });
      }
    );
    return () => {
      active = false;
    };
  }, []);

  const started = useRef(false);
  useEffect(() => {
    if (load.step !== "ready" || started.current) return;
    started.current = true;
    void runAnalyze();
  }, [load, runAnalyze]);

  // Mock mode assumes data so browser tests stay deterministic.
  useEffect(() => {
    if (!mock || started.current) return;
    started.current = true;
    setLoad({ step: "ready" });
    void runAnalyze();
  }, [mock, runAnalyze]);

  const retry = useCallback(() => {
    if (!pending) return;
    if (pending.type === "analyze") void runAnalyze();
    else if (pending.type === "recommend") void runRecommend();
    else void runQuestion(pending.text);
  }, [pending, runAnalyze, runRecommend, runQuestion]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">AI Analysis</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          A conversation about your training, grounded in your data.
        </p>
      </div>
      {load.step === "checking" ? (
        <p className="text-sm text-muted-foreground" role="status">
          Checking your training data…
        </p>
      ) : load.step === "no-dataset" ? (
        <div className="flex flex-col gap-4">
          <NoDataset context="AI analysis" />
          <p className="text-sm">
            <Link
              href="/#get-started"
              className="font-medium text-[var(--gold-bright)] underline-offset-4 hover:underline"
            >
              Try Out
            </Link>{" "}
            — upload your workout CSV and complete your profile, then
            return here.
          </p>
        </div>
      ) : load.step === "no-profile" ? (
        <div>
          <p className="text-sm leading-relaxed">
            I need your age, body weight and goal before analyzing your
            training.
          </p>
          <p className="mt-3 text-sm">
            <Link
              href="/#get-started"
              className="font-medium text-[var(--gold-bright)] underline-offset-4 hover:underline"
            >
              Complete your profile
            </Link>{" "}
            during onboarding, then return here.
          </p>
        </div>
      ) : (
        <AIConversation
          turns={turns}
          statusText={statusText}
          error={error}
          onRetry={retry}
          showRecommendAction={
            analysisText !== null && !recommendationsDone
          }
          recommending={recommending}
          onRecommend={() => void runRecommend()}
          onSend={(message) => void runQuestion(message)}
          sending={sending}
        />
      )}
    </main>
  );
}
