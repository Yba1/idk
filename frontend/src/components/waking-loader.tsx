// frontend/src/components/waking-loader.tsx
"use client";

import { useEffect, useState } from "react";
import { Brain } from "lucide-react";

const PHASES = [
  "Waking up the server…",
  "Warming up the retrieval index…",
  "Connecting to the language model…",
  "Almost ready…",
];

const PHASE_INTERVAL_MS = 1800;

export function WakingLoader() {
  const [revealed, setRevealed] = useState(1);

  useEffect(() => {
    if (revealed >= PHASES.length) return;
    const timer = setTimeout(() => setRevealed((n) => n + 1), PHASE_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [revealed]);

  return (
    <div className="flex flex-col items-center gap-5 py-4" role="status" aria-live="polite">
      <div className="relative flex h-20 w-20 items-center justify-center">
        <div className="brain-recharge-glow absolute inset-0 rounded-full" />
        <svg viewBox="0 0 80 80" className="brain-recharge-ring absolute inset-0 h-full w-full">
          <defs>
            <linearGradient id="chargeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="var(--accent-purple)" />
              <stop offset="100%" stopColor="var(--accent-pink)" />
            </linearGradient>
          </defs>
          <circle
            cx="40"
            cy="40"
            r="34"
            fill="none"
            stroke="url(#chargeGrad)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="120 213"
          />
        </svg>
        <Brain className="brain-recharge-icon relative h-8 w-8" style={{ color: "var(--accent-pink)" }} />
      </div>

      <div className="flex flex-col items-start gap-1.5">
        {PHASES.slice(0, revealed).map((phase, index) => {
          const isActive = index === revealed - 1;
          return (
            <div key={phase} className="brain-log-line flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${isActive ? "motion-safe:animate-pulse" : ""}`}
                style={{
                  background: isActive ? "var(--accent-pink)" : "var(--accent-purple)",
                  opacity: isActive ? 1 : 0.6,
                }}
              />
              <p className={`font-body text-xs ${isActive ? "text-ink" : "text-mist-dim"}`}>{phase}</p>
            </div>
          );
        })}
      </div>

      <p className="font-body text-[11px] text-mist-dim text-center max-w-xs">
        First request after inactivity can take up to a minute to spin up.
      </p>
    </div>
  );
}
