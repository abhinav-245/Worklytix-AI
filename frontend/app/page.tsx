import Image from "next/image";
import Link from "next/link";
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

/** Landing: immersive obsidian hero, onboarding, concise value props. */
export default function Home() {
  return (
    <main id="top" className="flex w-full flex-1 flex-col">
      <section className="hero-glow w-full overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-14 pb-16 sm:px-6 sm:pt-20 sm:pb-24 lg:grid-cols-[1.05fr_0.95fr] lg:gap-8">
          <div className="animate-obsidian-rise flex max-w-xl flex-col items-start gap-5 text-left">
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--gold-soft)] bg-[var(--gold-soft)] px-4 py-1 text-xs font-medium tracking-wide text-[var(--gold-bright)] uppercase">
              WorkLytix AI · Training analytics
            </span>
            <h1 className="text-4xl leading-[1.05] font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              TURN YOUR
              <br />
              TRAINING DATA
              <br />
              INTO{" "}
              <span className="text-gold-gradient">INTELLIGENCE.</span>
            </h1>
            <p className="max-w-md text-base text-muted-foreground sm:text-lg">
              Upload your workout history and transform it into
              measurable training insights.
            </p>
            <Link
              href="/#get-started"
              className="rounded-full bg-gradient-to-b from-[#F0C75E] to-[#B47A1B] px-6 py-3 text-sm font-semibold text-[#171207] shadow-[0_0_28px_rgba(212,164,58,0.35)] transition-all hover:brightness-110 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              Try Out
            </Link>
          </div>
          <div className="animate-obsidian-rise-delayed relative mx-auto w-full max-w-lg lg:max-w-none">
            <div
              aria-hidden
              className="absolute inset-0 -z-0 scale-90 rounded-full bg-[radial-gradient(circle,rgba(212,164,58,0.30),transparent_65%)] blur-2xl"
            />
            <Image
              src="/worklytix-runner.png"
              alt="WorkLytix AI gold runner emerging from a warm glow"
              width={1536}
              height={1024}
              priority
              sizes="(max-width: 1024px) 100vw, 50vw"
              className="relative z-10 w-full rounded-2xl border border-white/10 object-cover shadow-[0_24px_80px_rgba(0,0,0,0.6),0_0_60px_rgba(212,164,58,0.18)]"
            />
          </div>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col items-center gap-12 px-4 py-12 sm:px-6 sm:py-16">
        <Onboarding />

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
      </div>
    </main>
  );
}
