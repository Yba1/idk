"use client";

import { useEffect, useRef, useState } from "react";
import { Hero } from "@/components/hero";
import { QueryForm } from "@/components/query-form";
import { SourcedSummary } from "@/components/sourced-summary";
import { BrainViewer } from "@/components/brain-viewer";
import { ProfilePanel } from "@/components/memory/profile-panel";
import type { QueryResult } from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [profileRefresh, setProfileRefresh] = useState(0);
  const resultsRef = useRef<HTMLDivElement>(null);
  const citedConditionNames = result
    ? Array.from(new Set(result.papers.map((paper) => paper.paper.condition)))
    : [];

  useEffect(() => {
    if (result) {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  function handleResult(nextResult: QueryResult) {
    setResult(nextResult);
    setProfileRefresh((count) => count + 1);
  }

  return (
    <>
      <Hero />
      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-24 px-6 py-16 md:px-12">
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <QueryForm onResult={handleResult} />
          <ProfilePanel refreshKey={profileRefresh} />
        </div>

        <BrainViewer citedConditionNames={citedConditionNames} />

        {result && (
          <div ref={resultsRef}>
            <SourcedSummary result={result} />
          </div>
        )}
      </main>
    </>
  );
}
