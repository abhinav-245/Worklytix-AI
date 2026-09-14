import Image from "next/image";
import { cn } from "@/lib/utils";

/** WorkLytix AI runner mark in a restrained obsidian tile. */
export function BrandMark({ size = 36 }: { size?: number }) {
  return (
    <span
      aria-hidden
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#0A0A0A]"
      style={{ width: size, height: size }}
    >
      <Image
        src="/worklytix-runner.png"
        alt=""
        width={size}
        height={size}
        className="object-cover"
        priority={false}
      />
    </span>
  );
}

/** WorkLytix AI wordmark in the PP Pangaia brand voice. */
export function BrandWordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "font-brand text-[17px] leading-none font-medium whitespace-nowrap text-[#F5F5F5] sm:text-[1.35rem]",
        className
      )}
    >
      WorkLytix<span className="metric-gold"> AI</span>
    </span>
  );
}
