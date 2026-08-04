// frontend/src/components/hero.tsx
"use client";

import { NeuronCanvas } from "@/components/neuron-canvas";

export function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col overflow-hidden">
      <div
        className="absolute inset-0 z-0"
        aria-hidden="true"
        style={{
          WebkitMaskImage: "linear-gradient(to bottom, black, black 55%, transparent 100%)",
          maskImage: "linear-gradient(to bottom, black, black 55%, transparent 100%)",
        }}
      >
        <div
          className="absolute rounded-full blur-3xl"
          style={{
            top: "8%",
            left: "5%",
            width: "52%",
            height: "60%",
            background: "radial-gradient(circle, oklch(0.5 0.19 296 / 0.55), transparent 70%)",
          }}
        />
        <div
          className="absolute rounded-full blur-3xl"
          style={{
            bottom: "18%",
            right: "8%",
            width: "48%",
            height: "45%",
            background: "radial-gradient(circle, oklch(0.62 0.2 350 / 0.4), transparent 70%)",
          }}
        />
        <NeuronCanvas particleCount={46} rootX={0.68} rootY={0.42} />
      </div>

      <div className="relative z-[2] flex items-center justify-between px-6 py-9 md:px-12">
        <span className="font-body text-sm font-semibold uppercase tracking-[0.22em] text-ink">
          NeuLitTrace
        </span>
        <span className="rounded-full border border-line-bright bg-void-2/40 px-4 py-2 font-body text-xs tracking-[0.08em] text-mist backdrop-blur-md">
          Literature verification - not a diagnostic tool
        </span>
      </div>

      <div className="relative z-[2] flex flex-1 flex-col justify-center px-6 md:px-12 max-w-4xl">
        <span className="eyebrow mb-5">Retrieval, for the rare case</span>
        <h1 className="font-display font-medium text-ink leading-[1.05] text-[clamp(44px,7vw,88px)] mb-7">
          Trace the rare case
          <br />
          back to its source.
        </h1>
        <p className="font-body text-lg leading-relaxed text-paper max-w-xl">
          A literature-verification engine for rare PET and neuroimaging findings:
          weighted toward the underexplored, backed by citations at every step.
        </p>
      </div>

      <div className="relative z-[2] flex flex-col items-center gap-2 pb-9 font-body text-xs uppercase tracking-[0.1em] text-mist">
        <span>Scroll to explore</span>
        <div
          className="h-[22px] w-px motion-safe:animate-bounce"
          style={{ background: "linear-gradient(var(--accent-pink), transparent)" }}
        />
      </div>
    </section>
  );
}
