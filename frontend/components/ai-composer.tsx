"use client";

import { useState } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Persistent chat composer: multiline, Enter sends, Shift+Enter newline. */
export function AIComposer({
  onSend,
  sending,
  disabled,
}: {
  onSend: (message: string) => void;
  sending: boolean;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const inactive = sending || disabled;
  const canSend = draft.trim().length > 0 && !inactive;

  const send = () => {
    const message = draft.trim();
    if (!message || inactive) return;
    setDraft("");
    onSend(message);
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        aria-label="Ask a follow-up question"
        rows={2}
        maxLength={2000}
        value={draft}
        disabled={inactive}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder="Ask a follow-up question…"
        className={cn(
          "flex min-h-11 w-full resize-y rounded-xl border border-input bg-[#0A0A0A] px-3 py-2 text-sm shadow-sm transition-colors",
          "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50"
        )}
      />
      <Button
        onClick={send}
        disabled={!canSend}
        aria-label="Send message"
        className="shrink-0"
      >
        <SendHorizonal aria-hidden />
      </Button>
    </div>
  );
}
