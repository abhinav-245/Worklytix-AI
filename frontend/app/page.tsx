import { BackendStatus } from "@/components/backend-status";
import { CsvUpload } from "@/components/csv-upload";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-8">
      <h1 className="text-4xl font-bold tracking-tight">
        Fitness Intelligence
      </h1>
      <p className="max-w-md text-center text-lg text-muted-foreground">
        Fitness-data analysis application.
      </p>
      <BackendStatus />
      <CsvUpload />
    </main>
  );
}
