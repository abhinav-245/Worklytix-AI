import { redirect } from "next/navigation";

/** Legacy route: Ask My Training now lives in the AI Analysis conversation. */
export default function InsightsPage() {
  redirect("/ai-analysis");
}
