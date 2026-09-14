import { Activity, ChartLine, Dumbbell, UserRound } from "lucide-react";
import { Onboarding } from "@/components/onboarding";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const VALUE_PROPS = [
  {
    icon: Dumbbell,
    title: "PRs & volume",
    text: "Heaviest lifts, rep bests and total training volume per exercise.",
  },
  {
    icon: Activity,
    title: "Plateaus & muscles",
    text: "Stalled lifts surface with evidence; sets map to muscle groups.",
  },
  {
    icon: ChartLine,
    title: "Progression charts",
    text: "Weight, reps and estimated 1RM over time for every exercise.",
  },
  {
    icon: UserRound,
    title: "Observed history",
    text: "Training span and level derived from your data — never judged.",
  },
];

/** Landing: hero, unified onboarding card, concise value props. */
export default function Home() {
  return (
    <main
      id="top"
      className="mx-auto flex w-full max-w-6xl flex-1 flex-col items-center gap-12 px-4 py-12 sm:px-6 sm:py-16"
    >
      <div className="flex w-full flex-col items-center gap-10 lg:flex-row lg:items-start lg:justify-between lg:gap-12">
        <div className="flex max-w-xl flex-col items-start gap-5 text-left">
          <span className="inline-flex items-center gap-2 rounded-full border border-[var(--gold-soft)] bg-[var(--gold-soft)] px-4 py-1 text-xs font-medium tracking-wide text-[var(--gold)] uppercase">
            Training analytics
          </span>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            YOUR WORKOUTS.
            <br />
            REAL INSIGHTS.
          </h1>
          <p className="text-xl font-medium text-foreground">
            Train Smarter.
            <br />
            See the Bigger Picture.
          </p>
          <p className="max-w-md text-muted-foreground">
            Upload your workout history and transform it into measurable
            training insights.
          </p>
        </div>
        <Onboarding />
      </div>

      <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {VALUE_PROPS.map((prop) => (
          <Card key={prop.title} className="glass glass-hover">
            <CardHeader className="pb-2">
              <prop.icon
                className="h-5 w-5 text-[var(--gold)]"
                aria-hidden
              />
              <CardTitle className="text-sm font-medium">
                {prop.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{prop.text}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
