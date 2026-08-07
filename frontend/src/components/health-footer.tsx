"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";

const PORTS = ["retrieval", "llm", "memory", "ledger"] as const;

export function HealthFooter() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <footer className="relative z-10 mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-4 border-t border-line px-6 py-6 font-body text-xs text-mist md:px-12">
      <div className="flex flex-wrap gap-4" aria-label="Backend health">
        {PORTS.map((port) => (
          <span key={port} className="flex items-center gap-2" title={health?.ports[port].detail ?? "Status unavailable"}>
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                !health ? "bg-mist-dim" : health.ports[port].ok ? "bg-rare" : "bg-accent-pink"
              }`}
            />
            {port}
          </span>
        ))}
      </div>
      <Link href="/economy" className="text-paper underline hover:text-ink">Token economy dashboard</Link>
    </footer>
  );
}
