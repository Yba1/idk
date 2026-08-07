// frontend/src/components/masthead.tsx
import Link from "next/link";

export function Masthead() {
  return (
    <>
      <div className="h-1 w-full bg-ink" aria-hidden="true" />
      <header className="flex items-center justify-between border-b border-ink px-6 py-5 md:px-16">
        <span className="flex items-center gap-3">
          <span className="relative flex h-[26px] w-[26px] items-center justify-center">
            <span
              className="absolute inset-[-6px] rounded-[4px]"
              style={{
                background: "oklch(0.6781 0.1215 258.28 / 0.14)",
                boxShadow: "0 0 18px oklch(0.6781 0.1215 258.28 / 0.38)",
              }}
              aria-hidden="true"
            />
            <span className="relative h-[26px] w-[26px] rounded-[4px] bg-blue-500" />
          </span>
          <span className="flex flex-col">
            <span className="font-display text-[23px] font-semibold leading-none text-ink">Trace</span>
            <span className="mt-1 font-data text-[10px] text-dim">Corpus ed. 2026.08 · 329 papers</span>
          </span>
        </span>
        <div className="flex items-center gap-4">
          <Link href="/cost" className="font-body text-sm text-blue-700 hover:underline">
            Cost ledger
          </Link>
          <span className="rounded-[2px] border border-rule px-3 py-1.5 font-body text-xs text-dim">
            Literature verification, not a diagnostic tool
          </span>
        </div>
      </header>
    </>
  );
}
