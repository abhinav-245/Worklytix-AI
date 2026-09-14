import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/** Empty state shown when no dataset has been uploaded yet. */
export function NoDataset({ context }: { context: string }) {
  return (
    <Card className="glass w-full">
      <CardContent className="flex flex-col items-start gap-4 pt-6">
        <div>
          <p className="font-medium">No workout data yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload your Hevy CSV to see {context}.
          </p>
        </div>
        <Button asChild>
          <Link href="/#get-started">Upload your CSV</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
