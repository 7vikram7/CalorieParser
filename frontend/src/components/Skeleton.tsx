import { WAKING_UP_MESSAGE } from "@/lib/useSlowLoading";

function Bar({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-black/10 ${className}`} />;
}

/** A handful of pulsing rows, standing in for a list of cards while it loads. */
export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <Bar key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

/**
 * Drop-in replacement for a bare "Loading…" paragraph: shows skeleton rows
 * shaped like the content that's coming, and switches to the cold-start
 * explanation once `slow` (from useSlowLoading) flips true, so a long
 * Render wake-up doesn't just look like a stuck placeholder.
 */
export function LoadingState({ slow, rows = 3 }: { slow: boolean; rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      <SkeletonRows count={rows} />
      {slow && <p className="text-sm text-black/50">{WAKING_UP_MESSAGE}</p>}
    </div>
  );
}
