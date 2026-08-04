"use client";

import { useEffect, useRef, useState } from "react";
import { Hero } from "@/components/hero";
import { QueryForm } from "@/components/query-form";
import { SourcedSummary } from "@/components/sourced-summary";
import { BrainViewer } from "@/components/brain-viewer";
import { queryLiterature, type QueryResult } from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const resultsRef = useRef<HTMLDivElement>(null);
  const citedConditionNames = result
    ? Array.from(new Set(result.citations.map((c) => c.condition)))
    : [];

  useEffect(() => {
    if (result) {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  async function handleSuggestedConditionClick(conditionName: string) {
    const newQuery = `${currentQuery} ${conditionName}`.trim();
    try {
      const newResult = await queryLiterature(newQuery);
      setCurrentQuery(newQuery);
      setResult(newResult);
    } catch (error) {
      console.error("Failed to submit query with suggested condition:", error);
    }
  }

  return (
    <>
      <Hero />
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-24 px-6 py-16 md:px-12">
        <QueryForm
          onResult={setResult}
          onCurrentQueryChange={setCurrentQuery}
        />

        <BrainViewer citedConditionNames={citedConditionNames} />

        {result && (
          <div ref={resultsRef}>
            <SourcedSummary
              result={result}
              onSuggestedConditionClick={handleSuggestedConditionClick}
            />
          </div>
        )}
      </main>
    </>
  );
}
