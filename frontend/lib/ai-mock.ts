/** Deterministic AI fixtures for browser verification only.

When the AI Analysis page is opened with `?e2e_mock=1`, the UI uses
these canned responses instead of calling the backend. Never used in
production paths; no network, no API key, fully deterministic.
*/

import type {
  AIAnswer,
  AIRecommendations,
} from "@/lib/api";

export const MOCK_ANALYSIS: AIAnswer = {
  answer: [
    "# Your Training Analysis",
    "",
    "Your Bench Press weight PR is 75 kg, achieved on 2025-08-11.",
    "",
    "## Overall Training",
    "",
    "Steady training observed across the recorded period.",
    "",
    "## Performance & Strength",
    "",
    "Bench Press shows the strongest progression in the dataset.",
    "",
    "## Overall Assessment",
    "",
    "Consistent training with a clear strength focus.",
  ].join("\n"),
  observations: [
    {
      statement: "Your Bench Press weight PR is 75 kg.",
      fact_ids: ["pr:bench_press_barbell:weight_pr"],
    },
  ],
  assumptions: [],
  limitations: ["Mock mode: no live provider data."],
};

export const MOCK_RECOMMENDATIONS: AIRecommendations = {
  recommendations: [
    {
      recommendation: "Consider reviewing your current progression "
        + "strategy for Bench Press.",
      reason: "Your Bench Press weight PR is 75 kg.",
      fact_ids: ["pr:bench_press_barbell:weight_pr"],
    },
  ],
  observations: [
    {
      statement: "Your Bench Press weight PR is 75 kg.",
      fact_ids: ["pr:bench_press_barbell:weight_pr"],
    },
  ],
  assumptions: [],
  limitations: ["Mock mode: no live provider data."],
};

export function mockFollowUp(question: string): AIAnswer {
  const short =
    question.length > 80 ? `${question.slice(0, 80)}…` : question;
  return {
    answer: `You asked: "${short}"\n\nYour Bench Press weight PR is `
      + "75 kg, which remains the strongest recorded performance.",
    observations: [
      {
        statement: "Your Bench Press weight PR is 75 kg.",
        fact_ids: ["pr:bench_press_barbell:weight_pr"],
      },
    ],
    assumptions: [],
    limitations: ["Mock mode: no live provider data."],
  };
}
