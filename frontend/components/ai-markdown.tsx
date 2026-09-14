"use client";

import ReactMarkdown from "react-markdown";

/** Restrained markdown rendering for assistant messages (DM Sans). */
export function AIMarkdown({ text }: { text: string }) {
  return (
    <div className="ai-markdown">
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}
