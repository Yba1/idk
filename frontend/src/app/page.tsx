"use client";

import { useEffect, useRef, useState } from "react";
import { Masthead } from "@/components/masthead";
import { Hero } from "@/components/hero";
import { QueryForm } from "@/components/query-form";
import { SourcedSummary } from "@/components/sourced-summary";
import { BrainViewer } from "@/components/brain-viewer";
import { ProfilePanel } from "@/components/memory/profile-panel";
import type { QueryResult } from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
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
      <Masthead />
      <main className="flex flex-1 flex-col">
        <Hero />
        <QueryForm onResult={handleResult} onCurrentQueryChange={setLastQuery} />
        <BrainViewer citedConditionNames={citedConditionNames} />
        {result && (
          <div ref={resultsRef}>
            <SourcedSummary result={result} />
          </div>
        )}
        <ProfilePanel refreshKey={profileRefresh} result={result} lastQuery={lastQuery} />
      </main>
    </>
  );
}
