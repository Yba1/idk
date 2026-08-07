// frontend/src/components/hero.tsx
"use client";

import { NeuronCanvas } from "@/components/neuron-canvas";
import { SectionRail } from "@/components/section-rail";

function CornerTick({ className }: { className: string }) {
  return <span className={`absolute h-3 w-3 border-blue-300 ${className}`} aria-hidden="true" />;
}

export function Hero() {
  return (
    <section className="relative flex min-h-[760px] flex-col overflow-hidden">
      {/* 1. Glow blooms */}
      <div className="absolute inset-0 z-0" aria-hidden="true">
        <span
          className="absolute rounded-full blur-3xl motion-safe:animate-[hero-bloom-a_20s_ease-in-out_infinite]"
          style={{
            top: "5%",
            right: "4%",
            width: "44%",
            height: "48%",
            background: "radial-gradient(circle, oklch(0.6781 0.1215 258.28 / 0.32), transparent 72%)",
          }}
        />
        <span
          className="absolute rounded-full blur-3xl motion-safe:animate-[hero-bloom-b_26s_ease-in-out_infinite] [animation-delay:3s]"
          style={{
            bottom: "8%",
            right: "18%",
            width: "36%",
            height: "40%",
            background: "radial-gradient(circle, oklch(0.6781 0.1215 258.28 / 0.2), transparent 72%)",
          }}
        />
      </div>

      {/* 2. Neuron canvas */}
      <NeuronCanvas particleCount={54} rootX={0.7} rootY={1.0} className="absolute inset-0 z-[1] h-full w-full" />

      {/* 3. White veils - keep the copy legible without dimming the canvas */}
      <div
        className="pointer-events-none absolute inset-0 z-[2]"
        aria-hidden="true"
        style={{
          background:
            "linear-gradient(to bottom, rgba(255,255,255,0.96) 0%, rgba(255,255,255,0.72) 26%, rgba(255,255,255,0.12) 48%, transparent 64%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-y-0 left-0 z-[2] w-[56%]"
        aria-hidden="true"
        style={{
          background:
            "linear-gradient(to right, rgba(255,255,255,0.96) 0%, rgba(255,255,255,0.78) 46%, transparent 100%)",
        }}
      />

      {/* 4. Corner registration ticks */}
      <CornerTick className="left-10 top-10 border-l border-t" />
      <CornerTick className="right-10 top-10 border-r border-t" />
      <CornerTick className="bottom-10 left-10 border-b border-l" />
      <CornerTick className="bottom-10 right-10 border-b border-r" />

      {/* 5. Content */}
      <div className="relative z-[3] max-w-[1040px] px-6 pt-[88px] md:px-16">
        <SectionRail number="§00" eyebrow="Retrieval, for the rare case" />
        <h1 className="mt-5 font-display text-[clamp(44px,7vw,86px)] font-medium leading-[1.02] tracking-[-0.028em] text-ink">
          Trace the rare case
          <br />
          back to its source.
        </h1>
      </div>

      <div className="relative z-[3] mt-auto grid gap-14 px-6 pb-16 pt-[120px] md:grid-cols-[minmax(0,470px)_1fr_auto] md:items-end md:px-16">
        <p className="font-body text-[17px] leading-[1.7] text-trace-muted">
          Rare-weighted retrieval across 329 case reports in 14 conditions. Every sentence carries a
          numbered citation, and every citation is checked against its source abstract before you read it.
        </p>

        <a
          href="#query"
          className="inline-flex w-fit items-center gap-2 border-b border-ink pb-[7px] font-body text-sm font-semibold text-ink"
        >
          Begin a query <span className="font-data text-blue-700">↓</span>
        </a>

        <div className="flex gap-6 border-l border-rule pl-6">
          {[
            ["329", "CASE REPORTS"],
            ["14", "CONDITIONS"],
            ["4 of 4", "CLAIMS TRACED"],
          ].map(([value, label]) => (
            <div key={label} className="flex flex-col gap-1.5">
              <span className="font-data text-[19px] text-ink">{value}</span>
              <span className="font-body text-[10.5px] tracking-[0.1em] text-dim uppercase">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-[26px] left-6 z-[3] flex items-center gap-2 md:left-16">
        <span className="h-[5px] w-[5px] rounded-full bg-blue-500 motion-safe:animate-pulse" aria-hidden="true" />
        <span className="font-data text-[10px] text-dim">
          Live render · depth 5 · 8 primary · 0.72 decay · illustrative, not patient data
        </span>
      </div>
    </section>
  );
}
