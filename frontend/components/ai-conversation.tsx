"use client";

import { Sparkles } from "lucide-react";
import { AIComposer } from "@/components/ai-composer";
import { AIMarkdown } from "@/components/ai-markdown";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface ConversationTurn {
  id: number;
  role: "user" | "assistant";
  /** Eyebrow shown above assistant turns; user turns show none. */
  label?: string;
  /** Assistant content (markdown) or user message (plain text). */
  content: string;
}

/** Single conversational turn: user message or assistant response. */
function Turn({ turn }: { turn: ConversationTurn }) {
  if (turn.role === "user") {
    return (
      <div data-turn="user" className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-[var(--gold-soft)] px-4 py-2.5">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {turn.content}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div data-turn="assistant" className="flex gap-3">
      <span
        aria-hidden
        className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[var(--gold-soft)] text-xs font-semibold text-[var(--gold-bright)]"
      >
        W
      </span>
      <div className="min-w-0 flex-1">
        {turn.label ? (
          <p className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {turn.label}
          </p>
        ) : null}
        <AIMarkdown text={turn.content} />
      </div>
    </div>
  );
}

/**
 * Continuous AI conversation: analysis, recommendations and follow-up
 * turns with a persistent composer. Turns are content, not cards.
 */
export function AIConversation({
  turns,
  statusText,
  error,
  onRetry,
  showRecommendAction,
  recommending,
  onRecommend,
  onSend,
  sending,
  composerDisabled,
}: {
  turns: ConversationTurn[];
  statusText: string | null;
  error: string | null;
  onRetry: () => void;
  showRecommendAction: boolean;
  recommending: boolean;
  onRecommend: () => void;
  onSend: (message: string) => void;
  sending: boolean;
  composerDisabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div
        role="log"
        aria-label="AI Analysis conversation"
        aria-live="polite"
        className="flex flex-col gap-6"
      >
        {turns.map((turn) => (
          <Turn key={turn.id} turn={turn} />
        ))}
      </div>
      {showRecommendAction ? (
        <div className="flex">
          <Button
            variant="outline"
            onClick={onRecommend}
            disabled={recommending || sending}
            aria-label="Get recommendations"
            className="border-[var(--gold-soft)] text-[var(--gold-bright)] hover:bg-[var(--gold-soft)] hover:text-[var(--gold-bright)]"
          >
            <Sparkles aria-hidden />
            {recommending ? "Preparing recommendations…" : "Recommendations"}
          </Button>
        </div>
      ) : null}
      {statusText ? (
        <p className="text-sm text-muted-foreground" role="status">
          {statusText}
        </p>
      ) : null}
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>
            {error}{" "}
            <Button variant="link" onClick={onRetry} className="h-auto p-0">
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      <AIComposer
        onSend={onSend}
        sending={sending}
        disabled={composerDisabled}
      />
    </div>
  );
}
