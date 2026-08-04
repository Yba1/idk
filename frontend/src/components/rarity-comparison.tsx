// frontend/src/components/rarity-comparison.tsx
"use client";

import { useEffect, useState } from "react";
import { getDemoContrast, type ContrastPaper, type DemoContrast } from "@/lib/api";
import { SectionGlow } from "@/components/section-glow";

function Column({
  title,
  papers,
  rareCasePmid,
  variant,
}: {
  title: string;
  papers: ContrastPaper[];
  rareCasePmid: string;
  variant: "naive" | "weighted";
}) {
  const isWeighted = variant === "weighted";
  return (
    <div
      className="p-6 rounded-[20px]"
      style={{
        background: isWeighted ? "oklch(0.24 0.06 320 / 0.35)" : "oklch(0.2 0.04 300 / 0.4)",
        border: isWeighted ? "1px solid oklch(0.66 0.19 340 / 0.3)" : "1px solid var(--line)",
      }}
    >
      <h3
        className="font-body text-xs font-semibold uppercase mb-4"
        style={{ letterSpacing: "0.1em", color: isWeighted ? "var(--rare)" : "var(--mist)" }}
      >
        {title}
      </h3>
      <ol className="flex flex-col">
        {papers.map((paper, i) => {
          const isRare = paper.pmid === rareCasePmid;
          return (
            <li key={paper.pmid}>
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-baseline gap-3 mb-1.5 rounded-[10px] px-3 py-2.5 transition-colors hover:underline"
                style={{
                  background: isRare ? "oklch(0.72 0.19 350 / 0.14)" : "transparent",
                  border: isRare ? "1px solid oklch(0.72 0.19 350 / 0.4)" : "1px solid transparent",
                }}
              >
                <span
                  className="font-body text-xs font-bold inline-block"
                  style={{ minWidth: "18px", color: isRare ? "var(--rare)" : "var(--mist-dim)" }}
                >
                  {i + 1}
                </span>
                <span
                  className="font-body text-sm leading-snug"
                  style={{ color: isRare ? "var(--ink)" : "var(--paper)" }}
                >
                  {paper.title}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function RarityComparison() {
  const [data, setData] = useState<DemoContrast | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setError(false);
    getDemoContrast()
      .then((result) => {
        if (isMounted) setData(result);
      })
      .catch(() => {
        if (isMounted) setError(true);
      });
    return () => {
      isMounted = false;
    };
  }, [attempt]);

  if (error) {
    return (
      <div>
        <p className="font-body text-sm text-accent-pink mb-2">
          Comparison view degraded. The backend did not respond.
        </p>
        <button
          type="button"
          onClick={() => setAttempt((n) => n + 1)}
          className="font-body text-sm underline text-mist hover:text-white"
        >
          Retry
        </button>
      </div>
    );
  }
  if (!data) {
    return <p className="font-body text-sm text-mist">Loading comparison.</p>;
  }

  return (
    <div>
      <p className="mb-1 font-body text-sm text-mist">
        Demonstration: fixed reference query, not your search above.
      </p>
      <p className="mb-4 font-body text-sm text-mist italic">&ldquo;{data.query}&rdquo;</p>
      <SectionGlow className="grid grid-cols-1 gap-7 md:grid-cols-2">
        <Column title="Naive ranking" papers={data.naive} rareCasePmid={data.rare_case_pmid} variant="naive" />
        <Column
          title="Rarity-weighted ranking"
          papers={data.weighted}
          rareCasePmid={data.rare_case_pmid}
          variant="weighted"
        />
      </SectionGlow>
    </div>
  );
}
